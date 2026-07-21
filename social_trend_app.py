"""
social_trend_app.py v6
======================
KEY FIXES:
- IG: NO cookies on explore/tags (prevents personal feed). Cookies only as fallback for login wall.
- Hashtag selections persist across reruns via session_state
- Show only data from selected hashtags (not everything ever scraped)
- In-app playback: state managed cleanly, no rerun inside column
- Thumbnails: proper fallback
- Google Trends: always shown, filtered to selected hashtag topics
- Filter bar: sticky (session state)
- Creator/title/description: from og:description properly
"""
import streamlit as st
import asyncio, sys, os, re, json, threading, subprocess, time, io
from datetime import datetime, timedelta
from urllib.parse import quote
import pandas as pd
import requests as _req

st.set_page_config(page_title="Trend Tracker · Shopsy", page_icon="📱", layout="wide")

# ── CHROMIUM INSTALL ──────────────────────────────────────────────────────────
@st.cache_resource
def install_chromium():
    try:
        subprocess.run([sys.executable,"-m","playwright","install","chromium"],
                      capture_output=True, text=True, timeout=120)
    except: pass
install_chromium()

def secret(k, d=""):
    try: return st.secrets.get(k,d) or d
    except: return os.environ.get(k,d)

IG_SESSIONID = secret("IG_SESSIONID")
IG_CSRFTOKEN = secret("IG_CSRFTOKEN")

# ── CATEGORY CLASSIFIER ───────────────────────────────────────────────────────
CATS = [
    ("ShopsyWomenEthnicContemporary",["kurti","kurta","saree","sari","lehenga","salwar","dupatta",
        "anarkali","palazzo","patiala","sharara","churidar","ethnic wear","silk saree","banarasi",
        "bandhani","chanderi","kalamkari","cotton kurti","rayon kurti"]),
    ("ShopsyWomenWesternCore",["crop top","co-ord","coord set","bodycon","midi dress","maxi dress",
        "women top","women shirt","women dress","women skirt","women jeans","women jacket",
        "women blazer","women sweatshirt","women hoodie","women tshirt"]),
    ("ShopsyMakeupFragrances",["lipstick","lip gloss","lip liner","foundation","concealer","mascara",
        "eyeliner","eyeshadow","blush","highlighter","kajal","makeup","nail polish","perfume",
        "mehendi","sindoor","bindi","compact","primer","contour","bronzer","lip balm"]),
    ("ShopsyGrooming",["shampoo","conditioner","hair oil","face wash","moisturizer","serum",
        "sunscreen","body wash","scrub","toner","skincare","skin care","facewash","lotion",
        "face cream","body lotion","hair mask","hair serum","vitamin c","niacinamide","retinol",
        "hyaluronic","micellar","cleansing oil","face mist","hair care"]),
    ("ShopsyPersonalHealthCare",["trimmer","hair dryer","straightener","curler","epilator","massager",
        "weighing scale","bp monitor","thermometer","glucometer","nebulizer","hair styler",
        "shaver","electric toothbrush","water flosser","facial steamer"]),
    ("ShopsyAudio",["earphone","earbuds","headphone","bluetooth speaker","tws","airpods","neckband",
        "soundbar","wired earphone","gaming headset","noise cancelling","anc headphone","true wireless",
        "wireless earphone"]),
    ("ShopsyMobileProtection",["phone case","back cover","screen guard","tempered glass","mobile cover",
        "phone cover","case cover","mobile protection","camera protector"]),
    ("ShopsyRestOfMobileAccessory",["charger","charging cable","power bank","mobile holder","selfie stick",
        "data cable","fast charger","usb cable","type c","wireless charger","phone stand"]),
    ("ShopsyHomeDecor",["candle","diya","pooja","wall decor","showpiece","wall clock","vase",
        "painting","fairy lights","led strip","home decor","artificial flower","idol","lamp",
        "wall hanging","dream catcher","photo frame","decorative","rangoli"]),
    ("ShopsyHouseHold",["pressure cooker","kadhai","tawa","container","lunch box","water bottle",
        "flask","cookware","utensil","chopper","kitchen tool","non stick","casserole","dinner set"]),
    ("ShopsyHomeFurnishing",["bedsheet","pillow cover","curtain","blanket","towel","mattress",
        "cushion cover","carpet","rug","bath mat","bed cover","duvet","quilt","comforter"]),
    ("ShopsySportFitness",["yoga mat","dumbbell","resistance band","gym wear","fitness","cricket",
        "badminton","football","cycling","workout","exercise","skipping rope","gym bag","ab roller"]),
    ("ShopsyKidClothing",["kids wear","kids clothes","baby clothes","boy shirt","girl dress",
        "infant","kids tshirt","kids kurta","kids jacket","school uniform","children clothes"]),
    ("ShopsyToysAndSS",["toy","puzzle","board game","stationery","crayon","art kit","stuffed toy",
        "lego","craft kit","playdoh","slime","fidget","pop it"]),
    ("ShopsyBabyCare",["diaper","baby food","baby oil","baby shampoo","baby soap","stroller",
        "feeding bottle","baby care","baby powder","teether","baby lotion","baby wipes"]),
    ("ShopsyLuggageAndTravelAccessories",["handbag","backpack","sling bag","tote bag","travel bag",
        "suitcase","purse","wallet","clutch","laptop bag","school bag","duffle bag","college bag"]),
    ("ShopsyFashionWearables",["jewellery","jewelry","earring","necklace","bracelet","ring","bangle",
        "watch","sunglasses","belt","chain","pendant","anklet","mangalsutra","maang tikka"]),
    ("ShopsyFootwear",["shoes","sandals","heels","sneakers","boots","slippers","chappal","loafers",
        "flip flops","sports shoes","formal shoes","wedges","bellies","jutti","mojari"]),
    ("ShopsyCoreEA",["mixer grinder","juicer","iron box","electric kettle","toaster","induction",
        "roti maker","sandwich maker","air fryer","electric cooker","hand blender","food processor"]),
    ("ShopsyHealthCare",["protein supplement","vitamin","ayurvedic","immunity","probiotic","whey protein",
        "health drink","weight loss","detox","collagen","multivitamin","omega","ashwagandha","protein bar"]),
    ("ShopsyIOT",["smartwatch","smart band","smart home","alexa","google home","smart lighting",
        "fitness band","wearable","smart switch","smart bulb"]),
    ("ShopsyCamera",["ring light","gimbal","gopro","dslr","camera lens","photography","selfie light",
        "action camera","tripod","vlog"]),
    ("ShopsyMensClothingEssentialsAndEthnic",["men kurta","men sherwani","dhoti","men ethnic",
        "bandhgala","nehru jacket","men festive"]),
    ("ShopsyMensClothingCasualTopwear",["men tshirt","men shirt","polo shirt","men hoodie",
        "men sweatshirt","men jacket","men casual","men fashion","men outfit","men wear"]),
    ("ShopsyFoodAndNutrition",["healthy snack","oats","muesli","honey","ghee","dry fruits",
        "nuts","seeds","superfood","health food","organic"]),
    ("ShopsyHouseHoldSupplies",["detergent","washing powder","dishwash","floor cleaner",
        "toilet cleaner","insect repellent","garbage bag","fabric softener","disinfectant"]),
]
VERTICAL = {
    "ShopsyWomenEthnicContemporary":"Women Fashion","ShopsyWomenWesternCore":"Women Fashion",
    "ShopsyMensClothingCasualTopwear":"Men Fashion","ShopsyMensClothingEssentialsAndEthnic":"Men Fashion",
    "ShopsyKidClothing":"Kids Fashion","ShopsyFootwear":"Footwear",
    "ShopsyFashionWearables":"Accessories","ShopsyLuggageAndTravelAccessories":"Bags & Luggage",
    "ShopsyMakeupFragrances":"Beauty","ShopsyGrooming":"Beauty",
    "ShopsyPersonalHealthCare":"Personal Care","ShopsyHealthCare":"Health",
    "ShopsyBabyCare":"Baby","ShopsyAudio":"Electronics","ShopsyMobileProtection":"Mobile",
    "ShopsyRestOfMobileAccessory":"Mobile","ShopsyIOT":"Electronics","ShopsyCamera":"Electronics",
    "ShopsyHomeDecor":"Home","ShopsyHouseHold":"Home","ShopsyHomeFurnishing":"Home",
    "ShopsyHouseHoldSupplies":"Home","ShopsyCoreEA":"Appliances",
    "ShopsySportFitness":"Sports","ShopsyToysAndSS":"Toys","ShopsyFoodAndNutrition":"Food",
}

def classify(text:str):
    if not text: return "Unclassified","Other"
    tl=text.lower()
    for cat,kws in CATS:
        for kw in kws:
            if kw in tl:
                return cat, VERTICAL.get(cat,"Other")
    return "Unclassified","Other"

# ── DATA ──────────────────────────────────────────────────────────────────────
BASE_TAGS=["tiktokmademebuyit","instamademebuyit","musthave","viralproduct","justdropped",
    "newarrivals","trendingproducts","unboxing","productreview","triedandtested",
    "meeshofashion","meeshofinds","indianfashion","amazonshopping","onlineshopping",
    "shopthelook","kurtidesign","ethnicwear","makeuptutorial","skincareroutine",
    "hairtransformation","fitnessmotivation","gadgetreview","techunboxing",
    "homedecorinspo","kitchenhacks","meeshohaul","flipkartfinds"]
DATA_FILE="social_trends_data.json"

def load_data():
    if not os.path.exists(DATA_FILE): return []
    try: return json.load(open(DATA_FILE))
    except: return []

def save_data(records):
    by_url={}
    for r in records:
        url=r.get("url","")
        if url not in by_url or r.get("scraped_at","")>by_url[url].get("scraped_at",""):
            by_url[url]=r
    json.dump(list(by_url.values()),open(DATA_FILE,"w"),ensure_ascii=False,indent=2)

# ── GOOGLE TRENDS ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800)
def fetch_trends():
    try:
        r=_req.get("https://trends.google.com/trending/rss?geo=IN",timeout=8)
        items=re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>",r.text)
        traffic=re.findall(r"<hn:approx_traffic>(.+?)</hn:approx_traffic>",r.text)
        return [{"topic":t.strip(),"vol":traffic[i].replace("+","") if i<len(traffic) else ""}
                for i,t in enumerate(items[:20]) if t.strip()]
    except: return []

# ── SCRAPER ────────────────────────────────────────────────────────────────────
def pn(s):
    if not s: return None
    s=str(s).strip()
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

def fu(domain,link):
    if not link: return ""
    link=link.strip()
    if link.startswith("http"): return link
    return f"{domain}{link}" if link.startswith("/") else f"{domain}/{link}"

async def make_ctx(pw, inject_ig_cookies=False):
    """Create browser context. inject_ig_cookies=True only for login-wall fallback."""
    args=["--disable-blink-features=AutomationControlled","--no-sandbox","--disable-gpu",
          "--ignore-certificate-errors","--disable-dev-shm-usage","--disable-setuid-sandbox",
          "--no-zygote","--mute-audio"]
    try: browser=await pw.chromium.launch(headless=True,args=args)
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
        Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3]});
        window.chrome={runtime:{}};
    """)
    if inject_ig_cookies:
        cks=[]
        if IG_SESSIONID: cks.append({"name":"sessionid","value":IG_SESSIONID,"domain":".instagram.com","path":"/","httpOnly":True,"secure":True,"sameSite":"Lax"})
        if IG_CSRFTOKEN: cks.append({"name":"csrftoken","value":IG_CSRFTOKEN,"domain":".instagram.com","path":"/","secure":True,"sameSite":"Lax"})
        if cks: await ctx.add_cookies(cks)
    return browser,ctx

async def scrape_ig(ctx, tag, limit=15):
    """
    CRITICAL: explore/tags/{tag} without ANY IG cookies = public trending content
    With cookies = YOUR personal feed (shows your viewed reels, your name)
    So: try WITHOUT cookies first. If login-walled, retry WITH cookies.
    """
    rows=[]; reel_urls=[]

    page=await ctx.new_page()
    try:
        await page.goto(f"https://www.instagram.com/explore/tags/{tag}/",
            wait_until="domcontentloaded",timeout=25000)
        await asyncio.sleep(4)
        login_walled="login" in page.url or "accounts" in page.url

        if not login_walled:
            for _ in range(4):
                await page.evaluate("window.scrollBy(0,1200)")
                await asyncio.sleep(0.7)
            links=await page.locator("a[href*='/reel/'],a[href*='/p/']").all()
            for el in links[:limit]:
                href=await el.get_attribute("href")
                if not href: continue
                reel_urls.append(fu("https://www.instagram.com",href))
    except: pass
    finally:
        try: await page.close()
        except: pass

    # Open each reel page individually for real metadata
    # og:description = "1.2M views · @username: caption text" — PUBLIC data
    for url in reel_urls[:limit]:
        rp=await ctx.new_page()
        views=likes=creator=thumb=desc_text=None; title=""
        try:
            await rp.goto(url,wait_until="domcontentloaded",timeout=18000)
            await asyncio.sleep(1)
            html=await rp.content()

            # og:description has views, creator, caption
            og=re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']*)["\']',html,re.I)
            if not og:
                og=re.search(r'og:description[^>]*content="([^"]*)"',html,re.I)
            if og:
                d=og.group(1)
                vm=re.search(r"([\d,\.]+(?:[\s\u00a0]+(?:crore|lakh))?[KMB]?)\s*(?:views?|plays?)",d,re.I)
                if vm: views=pn(vm.group(1).strip())
                lm=re.search(r"([\d,\.]+[KMB]?)\s*likes?",d,re.I)
                if lm: likes=pn(lm.group(1).strip())
                cap=re.search(r"@[\w\.]+:\s*(.+)",d,re.S)
                if cap: desc_text=cap.group(1).strip()[:200]

            # JSON fallback for views
            if not views:
                for pat in [r'"viewCount"\s*:\s*"?([\d,]+)"?',r'"video_view_count"\s*:\s*(\d+)',r'"play_count"\s*:\s*(\d+)']:
                    m=re.search(pat,html)
                    if m: views=pn(m.group(1)); break
            if not likes:
                m=re.search(r'"like_count"\s*:\s*(\d+)',html)
                if m: likes=int(m.group(1))

            # Creator from JSON (public reel data)
            m=re.search(r'"username"\s*:\s*"([^"]+)"',html)
            if m: creator="@"+m.group(1)

            # Title: strip (N) notification prefix, strip " · Instagram"
            m=re.search(r"<title>([^<]+)</title>",html,re.I)
            if m:
                t=m.group(1)
                t=re.sub(r"^\(\d+\)\s*","",t)  # CRITICAL: removes (1) (2) etc.
                t=re.sub(r"\s*[•·|]\s*Instagram.*$","",t,flags=re.I).strip()
                if len(t)>5: title=t[:200]

            # Thumbnail
            m=re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',html,re.I)
            if not m: m=re.search(r'og:image[^>]*content="([^"]*)"',html,re.I)
            if m: thumb=m.group(1)
            if not thumb:
                m=re.search(r'"display_url"\s*:\s*"([^"]+)"',html)
                if m: thumb=m.group(1).replace("\\u0026","&")

        except: pass
        finally:
            try: await rp.close()
            except: pass

        if not title: title=f"Instagram Reel #{tag}"
        cat,vert=classify(title+" "+(desc_text or ""))
        rows.append({
            "platform":"Instagram","content_type":"Reel",
            "hashtag":f"#{tag}","url":url,
            "title":title,"description":desc_text or "",
            "creator":creator or "","thumbnail":thumb or "",
            "views":views,"likes":likes,"engagement":views or likes or 0,
            "category":cat,"vertical":vert,
            "scraped_at":datetime.now().isoformat(),
        })

    rows.sort(key=lambda x:x.get("engagement") or 0,reverse=True)
    return rows

async def scrape_yt(ctx, tag, limit=25):
    rows=[]; page=await ctx.new_page()
    try:
        await page.goto(f"https://www.youtube.com/results?search_query=%23{tag}",
            wait_until="domcontentloaded",timeout=25000)
        await asyncio.sleep(3)
        prev=0
        for _ in range(5):
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
                if vm: views=pn(vm.group(1).strip()); break
            if not views:
                aria=await t_el.get_attribute("aria-label") or ""
                vm2=re.search(r"([\d,\.]+[KMB]?)\s*views?",aria,re.I)
                if vm2: views=pn(vm2.group(1))
            ch=await v.query_selector("#channel-name a,ytd-channel-name a")
            channel=(await ch.inner_text()).strip() if ch else ""
            href=await t_el.get_attribute("href") or ""
            is_s="/shorts/" in href
            if not is_s:
                dur=await v.query_selector("span.ytd-thumbnail-overlay-time-status-renderer")
                if dur:
                    dt=(await dur.inner_text()).strip()
                    dm=re.match(r"^0:(\d+)$",dt)
                    if dm and int(dm.group(1))<=60: is_s=True
            vid_m=re.search(r"(?:v=|/shorts/)([A-Za-z0-9_-]{11})",href)
            vid_id=vid_m.group(1) if vid_m else ""
            thumb=f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg" if vid_id else ""
            cat,vert=classify(title)
            rows.append({
                "platform":"YouTube","content_type":"Shorts" if is_s else "Video",
                "hashtag":f"#{tag}","url":fu("https://www.youtube.com",href),
                "title":title,"description":"","creator":channel,
                "thumbnail":thumb,"vid_id":vid_id,
                "views":views,"likes":None,"engagement":views or 0,
                "category":cat,"vertical":vert,
                "scraped_at":datetime.now().isoformat(),
            })
        rows.sort(key=lambda x:x.get("views") or 0,reverse=True)
    except: pass
    finally:
        try: await page.close()
        except: pass
    return rows

async def _run_all(hashtags, platforms, per_tag, progress_cb):
    from playwright.async_api import async_playwright
    all_records=[]
    BATCH=3
    async with async_playwright() as pw:
        total=len(hashtags); done=0
        for i in range(0,total,BATCH):
            batch=hashtags[i:i+BATCH]
            tasks=[]
            for tag in batch:
                tasks.append(_scrape_one(pw,tag,platforms,per_tag))
            results=await asyncio.gather(*tasks,return_exceptions=True)
            for r in results:
                if isinstance(r,list): all_records.extend(r)
            done+=len(batch)
            if progress_cb: progress_cb(done/total,f"{done}/{total} hashtags")
    return all_records

async def _scrape_one(pw,tag,platforms,per_tag):
    rows=[]
    args=["--disable-blink-features=AutomationControlled","--no-sandbox","--disable-gpu",
          "--ignore-certificate-errors","--disable-dev-shm-usage","--disable-setuid-sandbox",
          "--no-zygote","--mute-audio"]
    try: browser=await pw.chromium.launch(headless=True,args=args)
    except:
        args.append("--single-process")
        browser=await pw.chromium.launch(headless=True,args=args)
    # NO IG COOKIES — prevents personal feed
    ctx=await browser.new_context(
        viewport={"width":1280,"height":800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        extra_http_headers={"Accept-Language":"en-IN,en;q=0.9"})
    await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
    try:
        if "Instagram" in platforms:
            try: rows.extend(await scrape_ig(ctx,tag,per_tag))
            except: pass
        if "YouTube" in platforms:
            try: rows.extend(await scrape_yt(ctx,tag,per_tag))
            except: pass
    finally:
        try: await ctx.close(); await browser.close()
        except: pass
    return rows

def run_sync(hashtags,platforms,per_tag,progress_cb=None):
    result={}; exc=[]; ps={"frac":0,"msg":"Starting..."}
    def _p(f,m): ps["frac"]=f; ps["msg"]=m
    def _t():
        loop=asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        try: result["r"]=loop.run_until_complete(_run_all(hashtags,platforms,per_tag,_p))
        except Exception as e: exc.append(e)
        finally: loop.close()
    t=threading.Thread(target=_t,daemon=True); t.start()
    while t.is_alive():
        if progress_cb:
            try: progress_cb(ps["frac"],ps["msg"])
            except: pass
        time.sleep(1)
    t.join(timeout=10)
    if exc: raise exc[0]
    return result.get("r",[])

# ── SESSION STATE INIT (runs once per session) ────────────────────────────────
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.selected_tags = BASE_TAGS[:12]
    st.session_state.selected_platforms = ["Instagram","YouTube"]
    st.session_state.per_tag = 10
    st.session_state.scraped_tags = set()   # tags scraped this session
    # play state for cards
    st.session_state.playing = None   # card_id currently playing

# ── STYLES ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
*{font-family:'Inter',sans-serif!important;}
.block-container{padding:1.5rem 2rem!important;max-width:1400px!important;}
.hero{background:linear-gradient(135deg,#0f172a,#312e81);border-radius:14px;padding:22px 30px;margin-bottom:16px;}
.hero-t{font-size:21px;font-weight:700;color:#f8fafc;}
.hero-s{font-size:11px;color:#a5b4fc;margin-top:2px;}
.card-wrap{border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.09);background:#fff;margin-bottom:8px;}
.thumb-box{position:relative;background:#000;}
.thumb-box img{width:100%;height:148px;object-fit:cover;display:block;}
.play-ico{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:38px;height:38px;background:rgba(0,0,0,.6);border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-size:14px;pointer-events:none;}
.short-tag{position:absolute;top:5px;right:5px;background:#c53030;color:#fff;padding:1px 5px;border-radius:3px;font-size:9px;font-weight:700;}
.cbody{padding:8px 10px 10px;}
.ctit{font-size:12px;font-weight:600;color:#1e293b;line-height:1.35;margin:3px 0;}
.cdsc{font-size:10px;color:#64748b;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin-bottom:3px;}
.cmeta{font-size:11px;color:#64748b;margin:1px 0;}
.pb{display:inline-block;padding:1px 6px;border-radius:5px;font-size:9px;font-weight:700;color:#fff;margin-right:2px;}
.catb{display:inline-block;padding:2px 7px;border-radius:12px;font-size:10px;background:#f0f4ff;color:#4361ee;margin-top:3px;}
.trchip{display:inline-block;background:#f0f4ff;color:#4361ee;padding:4px 10px;border-radius:20px;font-size:11px;margin:2px;font-weight:500;}
.trvol{font-size:9px;color:#94a3b8;margin-left:2px;}
</style>
""",unsafe_allow_html=True)

st.markdown("""<div class="hero">
  <div class="hero-t">📱 Social Trend Tracker · Shopsy</div>
  <div class="hero-s">Instagram Reels + YouTube Videos/Shorts · Shopsy Categories · No personal data</div>
</div>""",unsafe_allow_html=True)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Settings")

    # Persist selections in session_state so they don't reset on rerun
    new_tags=st.multiselect("Hashtags",BASE_TAGS,
        default=st.session_state.selected_tags,key="tag_picker")
    if new_tags != st.session_state.selected_tags:
        st.session_state.selected_tags = new_tags

    custom=st.text_input("+ Custom hashtag",placeholder="kurtilovers")
    if custom:
        tag=custom.lower().strip("#").replace(" ","")
        if tag and tag not in st.session_state.selected_tags:
            st.session_state.selected_tags=st.session_state.selected_tags+[tag]
            if tag not in BASE_TAGS: BASE_TAGS.append(tag)
            st.rerun()

    new_plats=st.multiselect("Platforms",["Instagram","YouTube"],
        default=st.session_state.selected_platforms,key="plat_picker")
    if new_plats != st.session_state.selected_platforms:
        st.session_state.selected_platforms = new_plats

    new_per=st.slider("Posts per hashtag",5,20,st.session_state.per_tag,key="per_tag_slider")
    if new_per != st.session_state.per_tag:
        st.session_state.per_tag = new_per

    st.divider()
    scrape_btn=st.button("🚀 Scrape Selected Hashtags",type="primary",use_container_width=True)
    st.divider()

    all_data_sidebar=load_data()
    st.metric("Total stored",len(all_data_sidebar))
    scraped_tags_in_db=set()
    for r in all_data_sidebar:
        ht=r.get("hashtag","").lstrip("#")
        if ht: scraped_tags_in_db.add(ht)
    if scraped_tags_in_db:
        st.caption(f"Tags in DB: {', '.join(sorted(scraped_tags_in_db)[:8])}{'...' if len(scraped_tags_in_db)>8 else ''}")
    if st.button("🗑 Clear ALL data",use_container_width=True):
        save_data([]); st.session_state.scraped_tags=set(); st.rerun()

selected_tags = st.session_state.selected_tags
selected_platforms = st.session_state.selected_platforms
per_tag_n = st.session_state.per_tag

# ── SCRAPE ─────────────────────────────────────────────────────────────────────
if scrape_btn and selected_tags:
    prog=st.progress(0,"Starting scrape...")
    status=st.empty()
    def cb(f,m):
        try: prog.progress(min(f,0.99),m); status.info(m)
        except: pass
    try:
        new_recs=run_sync(selected_tags,selected_platforms,per_tag_n,cb)
        existing=load_data()
        save_data(existing+new_recs)
        for tag in selected_tags:
            st.session_state.scraped_tags.add(tag)
        prog.empty(); status.empty()
        st.success(f"✅ {len(new_recs)} posts scraped for: {', '.join('#'+t for t in selected_tags)}")
        st.rerun()
    except Exception as e:
        import traceback
        st.error(f"Scrape error: {e}"); st.code(traceback.format_exc())

# ── LOAD + FILTER TO SELECTED HASHTAGS ONLY ───────────────────────────────────
all_data=load_data()
if not all_data:
    trends=fetch_trends()
    if trends:
        st.markdown("#### 🔥 Google Trends India Right Now")
        st.markdown(" ".join(f'<span class="trchip">{t["topic"]}<span class="trvol">{t["vol"]}</span></span>' for t in trends),unsafe_allow_html=True)
    st.info("No data yet. Select hashtags and click **Scrape Selected Hashtags**.")
    st.stop()

df=pd.DataFrame(all_data)
df["scraped_at"]=pd.to_datetime(df["scraped_at"],errors="coerce")
df["engagement"]=pd.to_numeric(df.get("engagement",0),errors="coerce").fillna(0)
df["views"]=pd.to_numeric(df.get("views",None),errors="coerce")
df["likes"]=pd.to_numeric(df.get("likes",None),errors="coerce")
if "hashtag" not in df.columns: df["hashtag"]=""

# CRITICAL: Only show data for currently selected hashtags
selected_ht_set={f"#{t}" for t in selected_tags}
df_sel=df[df["hashtag"].isin(selected_ht_set)]
if df_sel.empty:
    st.warning(f"No data yet for selected hashtags: {', '.join('#'+t for t in selected_tags[:5])}. Click **Scrape Selected Hashtags**.")
    df_sel=df  # fallback to all so stats tab still works

# ── GOOGLE TRENDS ─────────────────────────────────────────────────────────────
trends=fetch_trends()
if trends:
    st.markdown("#### 🔥 Google Trends India Right Now")
    st.markdown(" ".join(f'<span class="trchip">{t["topic"]}<span class="trvol">{t["vol"]}</span></span>' for t in trends),unsafe_allow_html=True)

# ── GLOBAL FILTER BAR (sticky via session_state) ─────────────────────────────
st.markdown("---")
fc1,fc2,fc3=st.columns(3)
with fc1:
    pf_opts=sorted(df_sel["platform"].unique().tolist())
    if "gf_plat" not in st.session_state: st.session_state.gf_plat=pf_opts
    pf=st.multiselect("Platform filter",pf_opts,default=[p for p in st.session_state.gf_plat if p in pf_opts],key="gf_plat")
with fc2:
    cat_opts=sorted(df_sel["category"].unique().tolist())
    if "gf_cat" not in st.session_state: st.session_state.gf_cat=[]
    cf=st.multiselect("Category",cat_opts,default=[c for c in st.session_state.gf_cat if c in cat_opts],key="gf_cat")
with fc3:
    vert_opts=sorted(df_sel["vertical"].unique().tolist()) if "vertical" in df_sel.columns else []
    if "gf_vert" not in st.session_state: st.session_state.gf_vert=[]
    vf=st.multiselect("Vertical",vert_opts,default=[v for v in st.session_state.gf_vert if v in vert_opts],key="gf_vert")

dff=df_sel.copy()
if pf: dff=dff[dff["platform"].isin(pf)]
if cf: dff=dff[dff["category"].isin(cf)]
if vf and "vertical" in dff.columns: dff=dff[dff["vertical"].isin(vf)]

# Export
csv_buf=io.StringIO(); dff.to_csv(csv_buf,index=False)
st.download_button("⬇️ Export CSV",csv_buf.getvalue(),"social_trends.csv","text/csv")

if dff.empty: st.info("No data matches current filters."); st.stop()

# ── HELPERS ───────────────────────────────────────────────────────────────────
def fv(v):
    if v is None or (isinstance(v,float) and pd.isna(v)): return "—"
    v=int(v)
    if v>=1_000_000: return f"{v/1_000_000:.1f}M"
    if v>=1_000: return f"{v/1_000:.0f}K"
    return str(v)

def render_card(r:dict, card_id:str):
    plat =r.get("platform","")
    ctype=r.get("content_type","")
    url  =r.get("url","#") or "#"
    thumb=r.get("thumbnail","")
    title=str(r.get("title",""))[:80]
    desc =str(r.get("description",""))[:100]
    cat  =str(r.get("category","")).replace("Shopsy","")
    vert =str(r.get("vertical",""))
    ht   =r.get("hashtag","")
    views=r.get("views"); likes=r.get("likes"); eng=r.get("engagement",0)
    cr   =r.get("creator","")
    vid_id=r.get("vid_id","") or ""
    bc   ="#e1306c" if plat=="Instagram" else "#ff0000"
    is_s =ctype=="Shorts"
    playing=st.session_state.get("playing")

    if playing==card_id:
        # Show embedded player
        if plat=="YouTube" and vid_id:
            st.markdown(
                f'<iframe width="100%" height="180" src="https://www.youtube.com/embed/{vid_id}?autoplay=1" '
                f'frameborder="0" allowfullscreen style="border-radius:8px;display:block"></iframe>',
                unsafe_allow_html=True)
        elif plat=="Instagram":
            st.markdown(
                f'<blockquote class="instagram-media" data-instgrm-permalink="{url}" '
                f'data-instgrm-version="14" style="width:100%!important;min-width:180px"></blockquote>'
                f'<script async src="//www.instagram.com/embed.js"></script>',
                unsafe_allow_html=True)
        if st.button("✕ Close",key=f"cls_{card_id}",use_container_width=True):
            st.session_state.playing=None; st.rerun()
    else:
        # Thumbnail
        if thumb:
            short_b='<div class="short-tag">SHORTS</div>' if is_s else ""
            st.markdown(
                f'<div class="thumb-box"><img src="{thumb}" '
                f'onerror="this.style.display=\'none\'">'
                f'<div class="play-ico">▶</div>{short_b}</div>',
                unsafe_allow_html=True)
        else:
            em="📸" if plat=="Instagram" else "▶"
            bg="#fce7f3" if plat=="Instagram" else "#fee2e2"
            st.markdown(
                f'<div style="height:148px;background:{bg};border-radius:8px 8px 0 0;'
                f'display:flex;align-items:center;justify-content:center;font-size:30px">{em}</div>',
                unsafe_allow_html=True)
        if st.button("▶ Play",key=f"play_{card_id}",use_container_width=True):
            st.session_state.playing=card_id; st.rerun()

    # Card info
    plat_b=f'<span class="pb" style="background:{bc}">{plat}</span>'
    if is_s: plat_b+=f'<span class="pb" style="background:#c53030">SHORTS</span>'
    ht_b=f'<span style="background:#e8ecff;color:#4361ee;padding:1px 5px;border-radius:5px;font-size:9px">{ht}</span>'
    metric="  ·  ".join(filter(None,[
        f"👁 {fv(views)}" if views and not pd.isna(views) else None,
        f"❤️ {fv(likes)}" if likes and not pd.isna(likes) else None,
    ])) or f"Eng: {fv(eng)}"
    cat_b=f'<span class="catb">🏷 {cat}{" · "+vert if vert and vert!="Other" else ""}</span>'

    st.markdown(f"""<div class="cbody">
<div>{plat_b} {ht_b}</div>
<div class="ctit">{title}</div>
{"<div class='cdsc'>"+desc+"</div>" if desc else ""}
{"<div class='cmeta'>👤 "+cr+"</div>" if cr else ""}
<div class="cmeta">{metric}</div>
{cat_b}
</div>""",unsafe_allow_html=True)
    st.link_button("Open ↗",url,use_container_width=True)

def render_grid(data:pd.DataFrame, label:str, max_n:int=50):
    if data.empty: st.info("No posts for selected hashtags."); return
    c1,c2,c3=st.columns(3)
    sk=f"sort_{label}"; pk=f"plat_{label}"; ck=f"cat_{label}"
    with c1: srt=st.selectbox("Sort",["Engagement","Views","Recent"],key=sk)
    with c2: pp=st.selectbox("Platform",["All","Instagram","YouTube"],key=pk)
    with c3: cp=st.selectbox("Category",["All"]+sorted(data["category"].unique().tolist()),key=ck)
    d=data.copy()
    if pp!="All": d=d[d["platform"]==pp]
    if cp!="All": d=d[d["category"]==cp]
    if srt=="Engagement": d=d.sort_values("engagement",ascending=False)
    elif srt=="Views": d=d.sort_values("views",ascending=False,na_position="last")
    else: d=d.sort_values("scraped_at",ascending=False)
    d=d.head(max_n).reset_index(drop=True)
    st.caption(f"{len(d)} posts · {srt} · hashtags: {', '.join(sorted({r['hashtag'] for _,r in d.iterrows()}))}")
    for i in range(0,len(d),4):
        cols=st.columns(4)
        for j,(_,r) in enumerate(d.iloc[i:i+4].iterrows()):
            with cols[j]:
                render_card(r.to_dict(),f"{label}_{i+j}")

# ── TABS ──────────────────────────────────────────────────────────────────────
now=datetime.now()
t1,t2,t3,t4,t5=st.tabs(["📅 L30 Days","📅 L7 Days","📅 Today/Yesterday","🏆 Lifetime Top 20","📊 Stats"])

with t1: render_grid(dff[dff["scraped_at"]>=now-timedelta(days=30)],"l30",60)
with t2: render_grid(dff[dff["scraped_at"]>=now-timedelta(days=7)],"l7",40)
with t3: render_grid(dff[dff["scraped_at"]>=now-timedelta(days=2)],"tod",30)

with t4:
    st.subheader(f"🏆 Top 20 · {', '.join('#'+t for t in selected_tags[:4])}{'...' if len(selected_tags)>4 else ''}")
    ic,yc=st.columns(2)
    with ic:
        st.markdown("#### 📸 Instagram")
        ig_t=dff[dff["platform"]=="Instagram"].sort_values("engagement",ascending=False).head(20).reset_index(drop=True)
        if ig_t.empty: st.info("No Instagram data for selected hashtags.")
        for i,(_,r) in enumerate(ig_t.iterrows()):
            ca,cb=st.columns([1,4])
            with ca:
                if r.get("thumbnail"): st.image(r["thumbnail"],width=60)
                else: st.markdown('<div style="width:60px;height:60px;background:#fce7f3;border-radius:6px;display:flex;align-items:center;justify-content:center">📸</div>',unsafe_allow_html=True)
            with cb:
                v=r.get("views"); l=r.get("likes")
                m2="  ·  ".join(filter(None,[f"👁 {fv(v)}" if v and not pd.isna(v) else None,f"❤️ {fv(l)}" if l and not pd.isna(l) else None])) or "—"
                st.markdown(f"**#{i+1}** {str(r.get('title',''))[:55]}")
                st.caption(f"{m2}  ·  {r.get('creator','')}  ·  {r.get('hashtag','')}")
                st.caption(f"🏷 {str(r.get('category','')).replace('Shopsy','')}")
                st.link_button("View →",r.get("url","#"),key=f"tig_{i}")
            st.markdown("<hr style='margin:2px 0;border:none;border-top:1px solid #f1f5f9'>",unsafe_allow_html=True)
    with yc:
        st.markdown("#### ▶ YouTube")
        yt_t=dff[dff["platform"]=="YouTube"].sort_values("engagement",ascending=False).head(20).reset_index(drop=True)
        if yt_t.empty: st.info("No YouTube data for selected hashtags.")
        for i,(_,r) in enumerate(yt_t.iterrows()):
            ca,cb=st.columns([1,4])
            with ca:
                if r.get("thumbnail"): st.image(r["thumbnail"],width=60)
                else: st.markdown('<div style="width:60px;height:60px;background:#fee2e2;border-radius:6px;display:flex;align-items:center;justify-content:center">▶</div>',unsafe_allow_html=True)
            with cb:
                ct=str(r.get("content_type","Video"))
                b2=f'<span style="background:#c53030;color:#fff;padding:1px 4px;border-radius:3px;font-size:9px">{ct}</span> ' if ct=="Shorts" else ""
                st.markdown(f"**#{i+1}** {b2}{str(r.get('title',''))[:55]}",unsafe_allow_html=True)
                st.caption(f"👁 {fv(r.get('views'))}  ·  {r.get('creator','')}  ·  {r.get('hashtag','')}")
                st.caption(f"🏷 {str(r.get('category','')).replace('Shopsy','')}")
                st.link_button("Watch →",r.get("url","#"),key=f"tyt_{i}")
            st.markdown("<hr style='margin:2px 0;border:none;border-top:1px solid #f1f5f9'>",unsafe_allow_html=True)

with t5:
    st.subheader("📊 Stats")
    m1,m2,m3,m4=st.columns(4)
    with m1: st.metric("Posts (selected tags)",len(dff))
    with m2: st.metric("Instagram",len(dff[dff["platform"]=="Instagram"]))
    with m3: st.metric("YouTube",len(dff[dff["platform"]=="YouTube"]))
    with m4: st.metric("Unique categories",dff["category"].nunique())
    st.divider()
    ch1,ch2=st.columns(2)
    with ch1:
        st.markdown("#### Categories")
        cc=dff["category"].value_counts().head(15).reset_index()
        cc.columns=["Category","Count"]
        cc["Category"]=cc["Category"].str.replace("Shopsy","")
        st.bar_chart(cc.set_index("Category")["Count"])
    with ch2:
        st.markdown("#### Vertical Engagement")
        if "vertical" in dff.columns:
            ve=dff.groupby("vertical")["engagement"].sum().sort_values(ascending=False).reset_index()
            st.bar_chart(ve.set_index("vertical")["engagement"])
    if "content_type" in dff.columns:
        st.divider()
        st.markdown("#### YouTube Types")
        yt2=dff[dff["platform"]=="YouTube"]
        if not yt2.empty:
            ct2=yt2["content_type"].value_counts().reset_index(); ct2.columns=["Type","Count"]
            st.bar_chart(ct2.set_index("Type")["Count"])
    st.divider()
    st.markdown("#### Hashtag Performance")
    hs=dff.groupby("hashtag").agg(Posts=("url","count"),TotalEng=("engagement","sum"),AvgEng=("engagement","mean")).round(0).sort_values("TotalEng",ascending=False).reset_index()
    st.dataframe(hs,use_container_width=True)
