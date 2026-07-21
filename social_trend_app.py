"""
social_trend_app.py v2
=======================
Streamlit social media trend tracker with cookie bypass for IG + Google.

SETUP (one-time):
1. In Chrome, log into instagram.com + google.com
2. Install "EditThisCookie" extension or use F12 → Application → Cookies
3. Copy cookie values
4. In Streamlit Cloud: Settings → Secrets → add:
   IG_SESSIONID = "your_value"
   IG_CSRFTOKEN = "your_value"
   GOOGLE_COOKIE = "your_value"  (the full cookie string from Chrome)

Run locally:
   streamlit run social_trend_app.py
"""

import streamlit as st
import asyncio, sys, os, re, json, threading, subprocess
from datetime import datetime, timedelta
from urllib.parse import quote
from pathlib import Path
import pandas as pd

st.set_page_config(
    page_title="Trend Tracker · Shopsy",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="expanded",
)

@st.cache_resource
def install_chromium():
    try:
        subprocess.run([sys.executable,"-m","playwright","install","chromium"],
                      capture_output=True, text=True, timeout=120)
        return "ok"
    except Exception as e:
        return str(e)
_ch = install_chromium()

# ── READ COOKIES FROM STREAMLIT SECRETS ──────────────────────────────────────
def get_secret(key, default=""):
    try:
        return st.secrets.get(key, default) or default
    except:
        return os.environ.get(key, default)

IG_SESSIONID  = get_secret("IG_SESSIONID")
IG_CSRFTOKEN  = get_secret("IG_CSRFTOKEN")
IG_DS_USER_ID = get_secret("IG_DS_USER_ID")
GOOGLE_COOKIE = get_secret("GOOGLE_COOKIE")  # full cookie header string

# ── SHOPSY CATEGORY CLASSIFIER ────────────────────────────────────────────────
CATEGORY_RULES = [
    ("ShopsyWomenEthnicContemporary", re.compile(
        r"\b(kurti|kurta|saree|sari|lehenga|salwar|dupatta|anarkali|ethnic|"
        r"palazzo|patiala|gharara|sharara|churidar|salwar kameez|suit set|"
        r"cotton kurti|printed kurti|rayon kurti|silk saree|banarasi)\b", re.I)),
    ("ShopsyWomenWesternCore", re.compile(
        r"\b(top|tshirt|t-shirt|crop top|dress|skirt|jeans|trouser|shorts|"
        r"jacket|blazer|sweatshirt|hoodie|co-ord|coord set|women western|"
        r"mini dress|maxi dress|shirt dress|bodycon)\b", re.I)),
    ("ShopsyMakeupFragrances", re.compile(
        r"\b(lipstick|lip gloss|lip liner|foundation|concealer|mascara|eyeliner|"
        r"eyeshadow|blush|highlighter|kajal|makeup|nail polish|perfume|deodorant|"
        r"mehendi|sindoor|bindi|compact|primer|contour)\b", re.I)),
    ("ShopsyGrooming", re.compile(
        r"\b(shampoo|conditioner|hair oil|face wash|moisturizer|serum|sunscreen|"
        r"body wash|scrub|toner|hair care|skin care|skincare|facewash|lotion|"
        r"face cream|body lotion|hair mask|hair serum|vitamin c|niacinamide|"
        r"retinol|hyaluronic|micellar water|cleansing oil)\b", re.I)),
    ("ShopsyPersonalHealthCare", re.compile(
        r"\b(trimmer|hair dryer|straightener|curler|epilator|massager|weighing scale|"
        r"blood pressure|thermometer|glucometer|nebulizer|hair styler|shaver|"
        r"electric toothbrush|water flosser|facial steamer)\b", re.I)),
    ("ShopsyAudio", re.compile(
        r"\b(earphone|earbuds|headphone|speaker|bluetooth|tws|airpods|"
        r"neckband|soundbar|wired earphone|gaming headset|true wireless|"
        r"noise cancelling|anc headphone)\b", re.I)),
    ("ShopsyMobileProtection", re.compile(
        r"\b(phone case|back cover|screen guard|tempered glass|mobile cover|"
        r"phone cover|case cover|mobile protection|camera protector)\b", re.I)),
    ("ShopsyRestOfMobileAccessory", re.compile(
        r"\b(charger|charging cable|power bank|mobile holder|selfie stick|"
        r"data cable|fast charger|usb cable|type c|wireless charger)\b", re.I)),
    ("ShopsyHomeDecor", re.compile(
        r"\b(candle|diya|pooja|wall decor|showpiece|wall clock|vase|painting|"
        r"fairy lights|led strip|home decor|artificial flower|idol|lamp|"
        r"wall hanging|dream catcher|photo frame|decorative)\b", re.I)),
    ("ShopsyHouseHold", re.compile(
        r"\b(pressure cooker|kadhai|tawa|container|lunch box|water bottle|flask|"
        r"cookware|utensil|chopper|mixer jar|grinder|kitchen tool|non stick|"
        r"casserole|dinner set|steel container)\b", re.I)),
    ("ShopsyHomeFurnishing", re.compile(
        r"\b(bedsheet|pillow|curtain|blanket|towel|mattress|cushion cover|"
        r"table cover|carpet|rug|bath mat|bed cover|duvet|quilt|comforter)\b", re.I)),
    ("ShopsySportFitness", re.compile(
        r"\b(yoga mat|dumbbell|resistance band|gym|fitness|cricket|badminton|"
        r"football|cycling|workout|exercise|skipping rope|gym bag|protein|whey|"
        r"gym gloves|ab roller)\b", re.I)),
    ("ShopsyKidClothing", re.compile(
        r"\b(kids wear|children|baby clothes|boy shirt|girl dress|infant|"
        r"kids tshirt|kids kurta|kids jacket|school uniform|baby outfit)\b", re.I)),
    ("ShopsyToysAndSS", re.compile(
        r"\b(toy|puzzle|board game|pen|notebook|stationery|crayon|art kit|"
        r"learning toy|remote control toy|stuffed toy|lego|craft|playdoh|slime)\b", re.I)),
    ("ShopsyBabyCare", re.compile(
        r"\b(baby|diaper|baby food|baby oil|baby shampoo|baby soap|stroller|"
        r"feeding bottle|baby care|infant care|baby powder|teether|baby lotion)\b", re.I)),
    ("ShopsyLuggageAndTravelAccessories", re.compile(
        r"\b(handbag|backpack|sling bag|tote|travel bag|suitcase|"
        r"purse|wallet|clutch|laptop bag|school bag|duffle|college bag)\b", re.I)),
    ("ShopsyFashionWearables", re.compile(
        r"\b(jewellery|jewelry|earring|necklace|bracelet|ring|bangle|watch|"
        r"sunglasses|belt|chain|pendant|anklet|mangalsutra|maang tikka)\b", re.I)),
    ("ShopsyFootwear", re.compile(
        r"\b(shoes|sandals|heels|sneakers|boots|slippers|chappal|footwear|"
        r"loafers|flip flops|sports shoes|formal shoes|wedges|bellies)\b", re.I)),
    ("ShopsyCoreEA", re.compile(
        r"\b(mixer grinder|juicer|iron|kettle|toaster|induction|roti maker|"
        r"sandwich maker|air fryer|electric cooker|hand blender|electric iron)\b", re.I)),
    ("ShopsyHealthCare", re.compile(
        r"\b(protein supplement|vitamin|ayurvedic|immunity|probiotic|whey protein|"
        r"health drink|weight loss|detox|collagen|multivitamin|protein bar|"
        r"omega|fish oil|ashwagandha|chyawanprash)\b", re.I)),
    ("ShopsyIOT", re.compile(
        r"\b(smartwatch|smart band|smart home|alexa|google home|smart lighting|"
        r"fitness band|wearable|smart switch|smart bulb|iot)\b", re.I)),
    ("ShopsyCamera", re.compile(
        r"\b(camera|tripod|ring light|gimbal|vlog|gopro|dslr|lens|photography|"
        r"selfie light|webcam|action camera)\b", re.I)),
    ("ShopsyMensClothingEssentialsAndEthnic", re.compile(
        r"\b(men kurta|men sherwani|dhoti|men ethnic|lungi|men pyjama|"
        r"bandhgala|nehru jacket|men ethnic wear|men festive)\b", re.I)),
    ("ShopsyMensClothingCasualTopwear", re.compile(
        r"\b(men tshirt|men shirt|polo shirt|men hoodie|men sweatshirt|men jacket|"
        r"men casual|men fashion|men wear|men outfit|men style)\b", re.I)),
    ("ShopsyFoodAndNutrition", re.compile(
        r"\b(food|snack|chocolate|tea|coffee|dry fruits|spices|healthy food|"
        r"protein bar|oats|muesli|honey|ghee|masala|nuts|seeds|superfood)\b", re.I)),
    ("ShopsyHouseHoldSupplies", re.compile(
        r"\b(detergent|washing powder|dishwash|floor cleaner|toilet cleaner|"
        r"insect repellent|garbage bag|kitchen cleaner|fabric softener|disinfectant)\b", re.I)),
]

VERTICAL_MAP = {
    "ShopsyWomenEthnicContemporary": "Women Fashion",
    "ShopsyWomenWesternCore": "Women Fashion",
    "ShopsyMensClothingCasualTopwear": "Men Fashion",
    "ShopsyMensClothingEssentialsAndEthnic": "Men Fashion",
    "ShopsyKidClothing": "Kids Fashion",
    "ShopsyFootwear": "Footwear",
    "ShopsyFashionWearables": "Accessories",
    "ShopsyLuggageAndTravelAccessories": "Bags & Luggage",
    "ShopsyMakeupFragrances": "Beauty",
    "ShopsyGrooming": "Beauty",
    "ShopsyPersonalHealthCare": "Personal Care",
    "ShopsyHealthCare": "Health",
    "ShopsyBabyCare": "Baby",
    "ShopsyAudio": "Electronics",
    "ShopsyMobileProtection": "Mobile",
    "ShopsyRestOfMobileAccessory": "Mobile",
    "ShopsyIOT": "Electronics",
    "ShopsyCamera": "Electronics",
    "ShopsyHomeDecor": "Home",
    "ShopsyHouseHold": "Home",
    "ShopsyHomeFurnishing": "Home",
    "ShopsyHouseHoldSupplies": "Home",
    "ShopsyCoreEA": "Appliances",
    "ShopsySportFitness": "Sports",
    "ShopsyToysAndSS": "Toys & Stationery",
    "ShopsyFoodAndNutrition": "Food",
}

def classify(text: str) -> tuple:
    if not text: return "Unclassified", "Other"
    for cat, pat in CATEGORY_RULES:
        if pat.search(text):
            return cat, VERTICAL_MAP.get(cat, "Other")
    return "Unclassified", "Other"

# ── BASE HASHTAGS ─────────────────────────────────────────────────────────────
BASE_HASHTAGS = [
    "tiktokmademebuyit","instamademebuyit","musthave","viralproduct",
    "justdropped","newarrivals","trendingproducts","unboxing",
    "productreview","triedandtested","meeshofashion","meeshofinds",
    "indianfashion","amazonshopping","onlineshopping","shopthelook",
    "kurtidesign","ethnicwear","makeuptutorial","skincareroutine",
    "hairtransformation","fitnessmotivation","gadgetreview","techunboxing",
    "homedecorinspo","kitchenhacks","meeshohaul","flipkartfinds",
]

DISCOVER_FILE = "discovered_hashtags.json"
DATA_FILE     = "social_trends_data.json"

def load_all_hashtags():
    tags = list(BASE_HASHTAGS)
    if os.path.exists(DISCOVER_FILE):
        try:
            d = json.load(open(DISCOVER_FILE))
            tags += d.get("tags", [])
        except: pass
    return list(dict.fromkeys(tags))

def save_discovered(new_tags):
    existing = []
    if os.path.exists(DISCOVER_FILE):
        try: existing = json.load(open(DISCOVER_FILE)).get("tags",[])
        except: pass
    merged = list(dict.fromkeys(existing + new_tags))[:300]
    json.dump({"tags":merged,"updated":datetime.now().isoformat()}, open(DISCOVER_FILE,"w"))

def load_data():
    if not os.path.exists(DATA_FILE): return []
    try: return json.load(open(DATA_FILE))
    except: return []

def save_data(records):
    by_url = {}
    for r in records:
        url = r.get("url","")
        if url not in by_url or r.get("scraped_at","") > by_url[url].get("scraped_at",""):
            by_url[url] = r
    json.dump(list(by_url.values()), open(DATA_FILE,"w"), ensure_ascii=False, indent=2)

# ── SCRAPER ────────────────────────────────────────────────────────────────────
def parse_num(s):
    if not s: return None
    s = str(s).strip()
    for pat,mul in [(r"([\d.]+)\s*crore",10_000_000),(r"([\d.]+)\s*lakh",100_000)]:
        m=re.search(pat,s,re.I)
        if m:
            try: return int(float(m.group(1))*mul)
            except: pass
    s2=s.upper().replace(",","")
    m=re.search(r"([\d.]+)\s*([KMB]?)",s2)
    if not m: return None
    try: return int(float(m.group(1))*{"K":1000,"M":1_000_000,"B":1_000_000_000}.get(m.group(2),1))
    except: return None

def fmt_url(domain,link):
    if not link: return ""
    link=link.strip()
    if link.startswith("http"): return link
    return f"{domain}{link}" if link.startswith("/") else f"{domain}/{link}"

async def make_context(pw):
    args=["--disable-blink-features=AutomationControlled","--no-sandbox","--disable-gpu",
          "--ignore-certificate-errors","--disable-dev-shm-usage","--disable-setuid-sandbox",
          "--no-zygote","--mute-audio","--disable-extensions"]
    try:
        browser=await pw.chromium.launch(headless=True,args=args)
    except:
        args.append("--single-process")
        browser=await pw.chromium.launch(headless=True,args=args)

    ctx=await browser.new_context(
        viewport={"width":1920,"height":1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        extra_http_headers={"Accept-Language":"en-IN,en;q=0.9,hi;q=0.8"})
    await ctx.add_init_script("""
        Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
        Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});
        Object.defineProperty(navigator,'languages',{get:()=>['en-IN','en','hi']});
        window.chrome={runtime:{}};
    """)

    # Inject IG cookies if available
    ig_cookies = []
    if IG_SESSIONID:
        ig_cookies += [
            {"name":"sessionid","value":IG_SESSIONID,"domain":".instagram.com",
             "path":"/","httpOnly":True,"secure":True,"sameSite":"Lax"},
        ]
    if IG_CSRFTOKEN:
        ig_cookies += [{"name":"csrftoken","value":IG_CSRFTOKEN,"domain":".instagram.com",
                        "path":"/","secure":True,"sameSite":"Lax"}]
    if IG_DS_USER_ID:
        ig_cookies += [{"name":"ds_user_id","value":IG_DS_USER_ID,"domain":".instagram.com",
                        "path":"/","secure":True,"sameSite":"Lax"}]
    if ig_cookies:
        await ctx.add_cookies(ig_cookies)

    # Inject Google cookie if available
    if GOOGLE_COOKIE:
        # Parse cookie string "name=value; name2=value2"
        g_cookies = []
        for part in GOOGLE_COOKIE.split(";"):
            part = part.strip()
            if "=" in part:
                name, _, value = part.partition("=")
                g_cookies.append({"name":name.strip(),"value":value.strip(),
                                   "domain":".google.com","path":"/",
                                   "secure":True,"sameSite":"Lax"})
        if g_cookies:
            await ctx.add_cookies(g_cookies)

    return browser, ctx

async def scrape_ig(ctx, tag, limit=20):
    rows=[]; reel_urls=[]
    page=await ctx.new_page()
    try:
        await page.goto(f"https://www.instagram.com/explore/tags/{tag}/",
            wait_until="domcontentloaded",timeout=25000)
        await asyncio.sleep(4)
        if "login" in page.url or "accounts" in page.url:
            return rows
        for _ in range(5):
            await page.evaluate("window.scrollBy(0,1200)")
            await asyncio.sleep(0.8)
        for el in (await page.locator("a[href*='/reel/'],a[href*='/p/']").all())[:limit]:
            href=await el.get_attribute("href")
            if not href: continue
            img_el=el.locator("img").first
            alt=(await img_el.get_attribute("alt") if await img_el.count() else "") or ""
            reel_urls.append((alt[:150],fmt_url("https://www.instagram.com",href)))
    except: pass
    finally:
        try: await page.close()
        except: pass

    for alt,url in reel_urls[:limit]:
        rp=await ctx.new_page(); views=likes=creator=thumb=None; title=alt
        try:
            await rp.goto(url,wait_until="domcontentloaded",timeout=18000)
            await asyncio.sleep(1)
            html=await rp.content()
            og=re.search(r'og:description[^>]*content="([^"]*)"',html,re.I)
            if og:
                desc=og.group(1)
                vm=re.search(r"([\d,\.]+(?:[\s\u00a0]+(?:crore|lakh))?[KMB]?)\s*(?:views?|plays?)",desc,re.I)
                if vm: views=parse_num(vm.group(1).strip())
                lm=re.search(r"([\d,\.]+[KMB]?)\s*likes?",desc,re.I)
                if lm: likes=parse_num(lm.group(1).strip())
            if not views:
                for pat in [r'"viewCount"\s*:\s*"?([\d,]+)"?',r'"video_view_count"\s*:\s*(\d+)',r'"play_count"\s*:\s*(\d+)']:
                    jv=re.search(pat,html)
                    if jv: views=parse_num(jv.group(1)); break
            if not likes:
                jl=re.search(r'"like_count"\s*:\s*(\d+)',html)
                if jl: likes=int(jl.group(1))
            cr=re.search(r'"username"\s*:\s*"([^"]+)"',html)
            if cr: creator="@"+cr.group(1)
            t_tag=re.search(r"<title>([^<]+)</title>",html,re.I)
            if t_tag:
                t=re.sub(r"\s*[•·|]\s*Instagram.*$","",t_tag.group(1),flags=re.I).strip()
                if len(t)>5: title=t[:200]
            og_img=re.search(r'og:image[^>]*content="([^"]*)"',html,re.I)
            if og_img: thumb=og_img.group(1)
        except: pass
        finally:
            try: await rp.close()
            except: pass
        cat,vert=classify(title)
        rows.append({"platform":"Instagram","hashtag":f"#{tag}","url":url,
            "title":title,"creator":creator or "","thumbnail":thumb or "",
            "views":views,"likes":likes,"engagement":views or likes or 0,
            "category":cat,"vertical":vert,"scraped_at":datetime.now().isoformat()})
    return rows

async def scrape_yt(ctx, tag, limit=25):
    rows=[]; page=await ctx.new_page()
    try:
        await page.goto(f"https://www.youtube.com/results?search_query=%23{tag}",
            wait_until="domcontentloaded",timeout=25000)
        await asyncio.sleep(3)
        prev=0
        for _ in range(6):
            await page.evaluate("window.scrollBy(0,3000)")
            await asyncio.sleep(1.2)
            vids=await page.query_selector_all("ytd-video-renderer,ytd-rich-item-renderer")
            if len(vids)>=limit or len(vids)==prev: break
            prev=len(vids)
        vids=await page.query_selector_all("ytd-video-renderer,ytd-rich-item-renderer")
        for v in vids[:limit]:
            t_el=await v.query_selector("#video-title,a#video-title")
            if not t_el: continue
            title=(await t_el.inner_text()).strip()
            if not title: continue
            views=None
            for span in await v.query_selector_all("#metadata-line span"):
                st2=(await span.inner_text()).strip()
                vm=re.search(r"([\d,\.]+(?:[\s\u00a0]+(?:crore|lakh))?[KMB]?)\s*views?",st2,re.I)
                if vm: views=parse_num(vm.group(1).strip()); break
            if not views:
                aria=await t_el.get_attribute("aria-label") or ""
                vm2=re.search(r"([\d,\.]+[KMB]?)\s*views?",aria,re.I)
                if vm2: views=parse_num(vm2.group(1))
            ch_el=await v.query_selector("#channel-name a,ytd-channel-name a")
            channel=(await ch_el.inner_text()).strip() if ch_el else ""
            href=await t_el.get_attribute("href") or ""
            vid_m=re.search(r"(?:v=|/shorts/)([A-Za-z0-9_-]{11})",href)
            thumb=f"https://img.youtube.com/vi/{vid_m.group(1)}/mqdefault.jpg" if vid_m else ""
            cat,vert=classify(title)
            rows.append({"platform":"YouTube","hashtag":f"#{tag}",
                "url":fmt_url("https://www.youtube.com",href),"title":title,
                "creator":channel,"thumbnail":thumb,"views":views,"likes":None,
                "engagement":views or 0,"category":cat,"vertical":vert,
                "scraped_at":datetime.now().isoformat()})
    except: pass
    finally:
        try: await page.close()
        except: pass
    return rows

async def get_trending_tags(ctx):
    tags=[]; page=await ctx.new_page()
    try:
        await page.goto("https://trends.google.com/trending/rss?geo=IN",
            wait_until="domcontentloaded",timeout=18000)
        body=await page.content()
        for g1,g2 in re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>|<title>(.+?)</title>",body)[1:21]:
            t=(g1 or g2).strip()
            if t:
                tag=re.sub(r"[^a-z0-9]","",t.lower())
                if 3<len(tag)<30: tags.append(tag)
    except: pass
    finally:
        try: await page.close()
        except: pass
    return tags[:10]

async def _run_all(hashtags, platforms, per_tag, progress_cb):
    from playwright.async_api import async_playwright
    all_records=[]; discovered=[]
    async with async_playwright() as pw:
        browser,ctx=await make_context(pw)
        # Discover trending tags
        try:
            discovered=await get_trending_tags(ctx)
        except: pass
        total=len(hashtags)
        for i,tag in enumerate(hashtags):
            if progress_cb: progress_cb(i/total, f"#{tag} ({i+1}/{total})")
            if "Instagram" in platforms:
                try:
                    rows=await scrape_ig(ctx,tag,per_tag)
                    all_records.extend(rows)
                except: pass
            if "YouTube" in platforms:
                try:
                    rows=await scrape_yt(ctx,tag,per_tag)
                    all_records.extend(rows)
                except: pass
            await asyncio.sleep(1)
        await ctx.close()
        await browser.close()
    return all_records,discovered

def run_sync(hashtags,platforms,per_tag,progress_cb=None):
    result={}; exc=[]; progress_state={"frac":0,"msg":"Starting..."}
    def _progress(frac, msg):
        progress_state["frac"]=frac; progress_state["msg"]=msg
    def _t():
        loop=asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        try: result["r"]=loop.run_until_complete(_run_all(hashtags,platforms,per_tag,_progress))
        except Exception as e: exc.append(e)
        finally: loop.close()
    t=threading.Thread(target=_t,daemon=True); t.start()
    import time
    while t.is_alive():
        if progress_cb:
            try: progress_cb(progress_state["frac"], progress_state["msg"])
            except: pass
        time.sleep(1)
    t.join(timeout=10)
    if exc: raise exc[0]
    return result.get("r",([],[]))

# ── STYLES ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
*{font-family:'Inter',sans-serif;}
.block-container{padding:1.5rem 2rem;max-width:1400px;}
.hero{background:linear-gradient(135deg,#0f172a,#312e81);border-radius:14px;padding:28px 36px;margin-bottom:20px;}
.hero-title{font-size:26px;font-weight:700;color:#f8fafc;}
.hero-sub{font-size:13px;color:#a5b4fc;margin-top:4px;}
.stat-chip{display:inline-block;background:#f0f4ff;color:#4361ee;padding:6px 14px;border-radius:20px;font-size:13px;margin:3px;font-weight:500;}
div[data-testid="stLinkButton"] a{font-size:12px!important;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <div class="hero-title">📱 Social Trend Tracker · Shopsy</div>
  <div class="hero-sub">Instagram Reels + YouTube Videos · Shopsy Category Classification · L30 / L7 / Today + Lifetime Top 20</div>
</div>""", unsafe_allow_html=True)

# Cookie status
has_ig  = bool(IG_SESSIONID)
has_goo = bool(GOOGLE_COOKIE)
st.markdown(
    f'<span class="stat-chip">{"✅" if has_ig else "⚠️"} Instagram cookies {"set" if has_ig else "not set"}</span>'
    f'<span class="stat-chip">{"✅" if has_goo else "⚠️"} Google cookies {"set" if has_goo else "not set"}</span>',
    unsafe_allow_html=True)
if not has_ig:
    with st.expander("ℹ️ How to set Instagram cookies (bypasses login wall)"):
        st.markdown("""
1. Open Chrome → log into **instagram.com**
2. Press `F12` → **Application** → **Cookies** → `instagram.com`
3. Copy these values:
   - `sessionid` (most important)
   - `csrftoken`
   - `ds_user_id`
4. In Streamlit Cloud: **Settings → Secrets** → add:
```toml
IG_SESSIONID = "your_sessionid_value"
IG_CSRFTOKEN = "your_csrftoken_value"
IG_DS_USER_ID = "your_ds_user_id_value"
```
5. Redeploy → full Instagram access, no login wall
        """)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Settings")
    all_tags = load_all_hashtags()
    selected = st.multiselect("Hashtags", options=all_tags, default=all_tags[:15])
    custom   = st.text_input("+ Add hashtag", placeholder="e.g. kurtilovers")
    if custom:
        tag = custom.lower().strip("#").replace(" ","")
        if tag and tag not in selected: selected.append(tag)
    platforms = st.multiselect("Platforms", ["Instagram","YouTube"], default=["Instagram","YouTube"])
    per_tag   = st.slider("Posts per hashtag", 5, 30, 15)
    st.divider()
    scrape_btn = st.button("🚀 Scrape Now", type="primary", use_container_width=True)
    st.divider()
    existing = load_data()
    st.metric("Stored records", len(existing))
    if existing:
        last = max(r.get("scraped_at","") for r in existing)
        st.caption(f"Last: {last[:16]}")
    if st.button("🗑 Clear data", use_container_width=True):
        save_data([]); st.rerun()

# ── SCRAPE ─────────────────────────────────────────────────────────────────────
if scrape_btn and selected:
    prog = st.progress(0, "Starting...")
    status = st.empty()
    def cb(frac, msg):
        prog.progress(min(frac,0.99), msg)
        status.info(msg)
    try:
        new_records, discovered = run_sync(selected, platforms, per_tag, cb)
        if discovered:
            save_discovered(discovered)
        existing = load_data()
        save_data(existing + new_records)
        prog.empty(); status.empty()
        st.success(f"✅ {len(new_records)} new posts scraped. Total: {len(load_data())} stored.")
        if discovered:
            st.info(f"📈 Trending tags discovered: {' '.join('#'+t for t in discovered[:5])}")
        st.rerun()
    except Exception as e:
        import traceback
        st.error(f"Error: {e}")
        st.code(traceback.format_exc())

# ── LOAD + FILTER ─────────────────────────────────────────────────────────────
all_data = load_data()
if not all_data:
    st.info("No data yet. Click **Scrape Now** in the sidebar to fetch content.")
    st.stop()

df = pd.DataFrame(all_data)
df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce")
df["engagement"] = pd.to_numeric(df.get("engagement",0), errors="coerce").fillna(0)
df["views"]      = pd.to_numeric(df.get("views",None), errors="coerce")
df["likes"]      = pd.to_numeric(df.get("likes",None), errors="coerce")

# Global filters
fc1,fc2,fc3 = st.columns(3)
with fc1:
    pf = st.multiselect("Platform filter", ["Instagram","YouTube"], default=["Instagram","YouTube"], key="gf_plat")
with fc2:
    all_cats = sorted(df["category"].unique().tolist())
    cf = st.multiselect("Category filter", all_cats, key="gf_cat")
with fc3:
    all_verts = sorted(df["vertical"].unique().tolist())
    vf = st.multiselect("Vertical filter", all_verts, key="gf_vert")

if pf: df = df[df["platform"].isin(pf)]
if cf: df = df[df["category"].isin(cf)]
if vf: df = df[df["vertical"].isin(vf)]
if df.empty: st.info("No data matches filters."); st.stop()

# ── HELPERS ───────────────────────────────────────────────────────────────────
def fv(v):
    if not v or pd.isna(v): return "—"
    v=int(v)
    if v>=1_000_000: return f"{v/1_000_000:.1f}M"
    if v>=1_000: return f"{v/1_000:.0f}K"
    return str(v)

def render_grid(data: pd.DataFrame, max_items: int = 40):
    if data.empty: st.info("No posts."); return
    c1,c2,c3 = st.columns(3)
    with c1:
        sort_opt = st.selectbox("Sort by",["Engagement","Views","Recent"], key=f"s_{id(data)}")
    with c2:
        plat_opt = st.selectbox("Platform",["All","Instagram","YouTube"], key=f"p_{id(data)}")
    with c3:
        cat_opt  = st.selectbox("Category",["All"]+sorted(data["category"].unique().tolist()), key=f"c_{id(data)}")

    d = data.copy()
    if plat_opt!="All": d=d[d["platform"]==plat_opt]
    if cat_opt!="All":  d=d[d["category"]==cat_opt]
    if sort_opt=="Engagement": d=d.sort_values("engagement",ascending=False)
    elif sort_opt=="Views": d=d.sort_values("views",ascending=False,na_position="last")
    elif sort_opt=="Recent": d=d.sort_values("scraped_at",ascending=False)
    d=d.head(max_items)

    st.caption(f"{len(d)} posts · sort: {sort_opt}")
    rows_of_4 = [d.iloc[i:i+4] for i in range(0,len(d),4)]
    for row in rows_of_4:
        cols=st.columns(4)
        for col,(_,r) in zip(cols,row.iterrows()):
            with col:
                plat  = r.get("platform","")
                url   = r.get("url","#") or "#"
                thumb = r.get("thumbnail","")
                title = str(r.get("title",""))[:70]
                cat   = str(r.get("category","")).replace("Shopsy","")
                ht    = r.get("hashtag","")
                views = r.get("views")
                likes = r.get("likes")
                eng   = r.get("engagement",0)
                cr    = r.get("creator","")
                col_badge = "#e1306c" if plat=="Instagram" else "#ff0000"

                if thumb:
                    st.image(thumb, use_container_width=True)
                else:
                    st.markdown(f'<div style="height:100px;background:#f1f5f9;border-radius:8px;'
                                f'display:flex;align-items:center;justify-content:center;font-size:28px">'
                                f'{"📸" if plat=="Instagram" else "▶"}</div>', unsafe_allow_html=True)

                st.markdown(
                    f'<span style="background:{col_badge};color:#fff;padding:1px 6px;'
                    f'border-radius:8px;font-size:10px;font-weight:700">{plat}</span> '
                    f'<span style="background:#e8ecff;color:#4361ee;padding:1px 6px;'
                    f'border-radius:8px;font-size:10px">{ht}</span>',
                    unsafe_allow_html=True)
                st.markdown(f"**{title}**")
                if cr: st.caption(cr)
                metric = "  ·  ".join(filter(None,[
                    f"👁 {fv(views)}" if views and not pd.isna(views) else None,
                    f"❤️ {fv(likes)}" if likes and not pd.isna(likes) else None,
                ])) or f"Eng: {fv(eng)}"
                st.caption(f"{metric}")
                st.caption(f"🏷 {cat}")

                # Open + embed buttons
                bc1,bc2 = st.columns(2)
                with bc1:
                    st.link_button("Open", url, use_container_width=True)
                with bc2:
                    key = f"e_{hash(url)}"
                    if st.button("▶", key=key, use_container_width=True):
                        st.session_state[key+"_show"] = not st.session_state.get(key+"_show",False)

                if st.session_state.get(f"e_{hash(url)}_show",False):
                    if plat=="YouTube":
                        vid_m=re.search(r"(?:v=|/shorts/)([A-Za-z0-9_-]{11})",url)
                        if vid_m:
                            st.markdown(f'<iframe width="100%" height="180" src="https://www.youtube.com/embed/{vid_m.group(1)}" frameborder="0" allowfullscreen></iframe>', unsafe_allow_html=True)
                        else:
                            st.link_button("Watch on YouTube", url)
                    elif plat=="Instagram":
                        clean=url.split("?")[0].rstrip("/")
                        st.markdown(f'<blockquote class="instagram-media" data-instgrm-permalink="{url}" data-instgrm-version="14" style="width:100%!important;min-width:200px"></blockquote><script async src="//www.instagram.com/embed.js"></script>', unsafe_allow_html=True)

# ── TABS ──────────────────────────────────────────────────────────────────────
now = datetime.now()
t30,t7,tod,top20,stats = st.tabs([
    "📅 Last 30 Days","📅 Last 7 Days","📅 Today / Yesterday",
    "🏆 Lifetime Top 20","📊 Category Stats"
])

with t30:
    st.subheader("Last 30 Days")
    d30 = df[df["scraped_at"] >= now-timedelta(days=30)]
    render_grid(d30, 60)

with t7:
    st.subheader("Last 7 Days")
    d7 = df[df["scraped_at"] >= now-timedelta(days=7)]
    render_grid(d7, 40)

with tod:
    st.subheader("Today & Yesterday")
    dt = df[df["scraped_at"] >= now-timedelta(days=2)]
    render_grid(dt, 30)

with top20:
    st.subheader("🏆 Lifetime Top 20 by Engagement")
    ig_col, yt_col = st.columns(2)

    with ig_col:
        st.markdown("#### 📸 Instagram")
        ig_top = df[df["platform"]=="Instagram"].sort_values("engagement",ascending=False).head(20)
        if ig_top.empty:
            st.info("No Instagram data yet.")
        for i,(_,r) in enumerate(ig_top.iterrows(),1):
            c1,c2 = st.columns([1,4])
            with c1:
                if r.get("thumbnail"): st.image(r["thumbnail"], width=65)
                else: st.markdown('<div style="width:65px;height:65px;background:#fce7f3;border-radius:8px;display:flex;align-items:center;justify-content:center">📸</div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f"**#{i}** {str(r.get('title',''))[:60]}")
                views = r.get("views"); likes = r.get("likes")
                m = "  ·  ".join(filter(None,[
                    f"👁 {fv(views)}" if views and not pd.isna(views) else None,
                    f"❤️ {fv(likes)}" if likes and not pd.isna(likes) else None,
                ])) or f"Eng: {fv(r.get('engagement'))}"
                st.caption(f"{m}  ·  {r.get('creator','')}  ·  {r.get('hashtag','')}")
                st.caption(f"🏷 {str(r.get('category','')).replace('Shopsy','')}")
                st.link_button("View →", r.get("url","#"))
            st.markdown("<hr style='margin:4px 0;border:none;border-top:1px solid #f1f5f9'>", unsafe_allow_html=True)

    with yt_col:
        st.markdown("#### ▶ YouTube")
        yt_top = df[df["platform"]=="YouTube"].sort_values("engagement",ascending=False).head(20)
        if yt_top.empty:
            st.info("No YouTube data yet.")
        for i,(_,r) in enumerate(yt_top.iterrows(),1):
            c1,c2 = st.columns([1,4])
            with c1:
                if r.get("thumbnail"): st.image(r["thumbnail"], width=65)
                else: st.markdown('<div style="width:65px;height:65px;background:#fee2e2;border-radius:8px;display:flex;align-items:center;justify-content:center">▶</div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f"**#{i}** {str(r.get('title',''))[:60]}")
                st.caption(f"👁 {fv(r.get('views'))}  ·  {r.get('creator','')}  ·  {r.get('hashtag','')}")
                st.caption(f"🏷 {str(r.get('category','')).replace('Shopsy','')}")
                st.link_button("Watch →", r.get("url","#"))
            st.markdown("<hr style='margin:4px 0;border:none;border-top:1px solid #f1f5f9'>", unsafe_allow_html=True)

with stats:
    st.subheader("📊 Category & Vertical Stats")
    m1,m2,m3,m4 = st.columns(4)
    with m1: st.metric("Total Posts",len(df))
    with m2: st.metric("Instagram",len(df[df["platform"]=="Instagram"]))
    with m3: st.metric("YouTube",len(df[df["platform"]=="YouTube"]))
    with m4: st.metric("Categories",df["category"].nunique())
    st.divider()

    ch1,ch2 = st.columns(2)
    with ch1:
        st.markdown("#### Top Categories (post count)")
        cc=df["category"].value_counts().head(15).reset_index()
        cc.columns=["Category","Count"]
        cc["Category"]=cc["Category"].str.replace("Shopsy","")
        st.bar_chart(cc.set_index("Category")["Count"])
    with ch2:
        st.markdown("#### Vertical Engagement")
        ve=df.groupby("vertical")["engagement"].sum().sort_values(ascending=False).reset_index()
        ve.columns=["Vertical","Engagement"]
        st.bar_chart(ve.set_index("Vertical")["Engagement"])

    st.divider()
    st.markdown("#### Full Category Breakdown")
    cs=df.groupby(["category","vertical","platform"]).agg(
        Posts=("url","count"),
        AvgEng=("engagement","mean"),
        TotalEng=("engagement","sum"),
    ).round(0).reset_index().sort_values("TotalEng",ascending=False)
    cs["category"]=cs["category"].str.replace("Shopsy","")
    st.dataframe(cs, use_container_width=True, height=400)

    st.divider()
    st.markdown("#### Hashtag Performance")
    hs=df.groupby("hashtag").agg(
        Posts=("url","count"),
        TotalEng=("engagement","sum"),
        AvgEng=("engagement","mean"),
    ).round(0).sort_values("TotalEng",ascending=False).reset_index()
    st.dataframe(hs, use_container_width=True)
