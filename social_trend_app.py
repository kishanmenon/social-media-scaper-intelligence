"""
social_trend_app.py v7
Key fixes:
- YouTube was blocked by login_walled check bleeding into YT scraper — fixed
- Tabs show same data because all scraped today — now shows distinct counts with proper date labels
- Playback: single session_state.playing key, rerun ONLY from button handlers (not inside render)
- Description + posted_on: extracted properly from og:description
- Classification: classify on title+description+hashtag combined text
- Google Trends: separate tab with L30/L7/L1 trend views
- No personal IG data: zero cookies in scraping context
"""
import streamlit as st
import asyncio, sys, os, re, json, threading, subprocess, time, io
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
import pandas as pd
import requests as _req

st.set_page_config(page_title="Trend Tracker · Shopsy", page_icon="📱", layout="wide")

@st.cache_resource
def install_chromium():
    try:
        subprocess.run([sys.executable,"-m","playwright","install","chromium"],
                      capture_output=True,text=True,timeout=120)
    except: pass
install_chromium()

def secret(k,d=""):
    try: return st.secrets.get(k,d) or d
    except: return os.environ.get(k,d)

IG_SESSIONID=secret("IG_SESSIONID")
IG_CSRFTOKEN=secret("IG_CSRFTOKEN")

# ── CATEGORIES ────────────────────────────────────────────────────────────────
CATS=[
    ("ShopsyWomenEthnicContemporary",["kurti","kurta","saree","sari","lehenga","salwar",
        "dupatta","anarkali","palazzo","patiala","sharara","churidar","ethnic wear",
        "silk saree","banarasi","bandhani","chanderi","cotton kurti","rayon kurti"]),
    ("ShopsyWomenWesternCore",["crop top","co-ord","coord set","bodycon","midi dress",
        "maxi dress","women top","women shirt","women dress","women skirt","women jeans",
        "women jacket","women blazer","women hoodie","women tshirt"]),
    ("ShopsyMakeupFragrances",["lipstick","lip gloss","lip liner","foundation","concealer",
        "mascara","eyeliner","eyeshadow","blush","highlighter","kajal","makeup","nail polish",
        "perfume","mehendi","bindi","compact","primer","contour","bronzer"]),
    ("ShopsyGrooming",["shampoo","conditioner","hair oil","face wash","moisturizer","serum",
        "sunscreen","body wash","scrub","toner","skincare","skin care","facewash","lotion",
        "face cream","body lotion","hair mask","hair serum","vitamin c","niacinamide",
        "retinol","hyaluronic","micellar","cleansing","face mist","hair care"]),
    ("ShopsyPersonalHealthCare",["trimmer","hair dryer","straightener","curler","epilator",
        "massager","weighing scale","bp monitor","thermometer","glucometer","nebulizer",
        "hair styler","shaver","electric toothbrush","water flosser","facial steamer"]),
    ("ShopsyAudio",["earphone","earbuds","headphone","bluetooth speaker","tws","airpods",
        "neckband","soundbar","wired earphone","gaming headset","noise cancelling",
        "anc headphone","true wireless","wireless earphone"]),
    ("ShopsyMobileProtection",["phone case","back cover","screen guard","tempered glass",
        "mobile cover","phone cover","case cover","camera protector"]),
    ("ShopsyRestOfMobileAccessory",["charger","charging cable","power bank","mobile holder",
        "selfie stick","data cable","fast charger","usb cable","type c","wireless charger"]),
    ("ShopsyHomeDecor",["candle","diya","pooja","wall decor","showpiece","wall clock","vase",
        "painting","fairy lights","led strip","home decor","artificial flower","idol","lamp",
        "wall hanging","dream catcher","photo frame","decorative","rangoli"]),
    ("ShopsyHouseHold",["pressure cooker","kadhai","tawa","container","lunch box",
        "water bottle","flask","cookware","utensil","chopper","kitchen tool","non stick",
        "casserole","dinner set"]),
    ("ShopsyHomeFurnishing",["bedsheet","pillow cover","curtain","blanket","towel",
        "mattress","cushion cover","carpet","rug","bath mat","bed cover","duvet","quilt"]),
    ("ShopsySportFitness",["yoga mat","dumbbell","resistance band","gym wear","fitness",
        "cricket","badminton","football","cycling","workout","exercise","skipping rope",
        "gym bag","ab roller","protein shaker"]),
    ("ShopsyKidClothing",["kids wear","kids clothes","baby clothes","boy shirt","girl dress",
        "infant","kids tshirt","kids kurta","kids jacket","school uniform","children"]),
    ("ShopsyToysAndSS",["toy","puzzle","board game","stationery","crayon","art kit",
        "stuffed toy","lego","craft","playdoh","slime","fidget","pop it"]),
    ("ShopsyBabyCare",["diaper","baby food","baby oil","baby shampoo","baby soap",
        "stroller","feeding bottle","baby care","baby powder","teether","baby lotion"]),
    ("ShopsyLuggageAndTravelAccessories",["handbag","backpack","sling bag","tote bag",
        "travel bag","suitcase","purse","wallet","clutch","laptop bag","school bag",
        "duffle bag","college bag","office bag"]),
    ("ShopsyFashionWearables",["jewellery","jewelry","earring","necklace","bracelet",
        "ring","bangle","watch","sunglasses","belt","chain","pendant","anklet",
        "mangalsutra","maang tikka"]),
    ("ShopsyFootwear",["shoes","sandals","heels","sneakers","boots","slippers","chappal",
        "loafers","flip flops","sports shoes","formal shoes","wedges","bellies","jutti"]),
    ("ShopsyCoreEA",["mixer grinder","juicer","iron box","electric kettle","toaster",
        "induction","roti maker","sandwich maker","air fryer","electric cooker",
        "hand blender","food processor"]),
    ("ShopsyHealthCare",["protein supplement","vitamin","ayurvedic","immunity","probiotic",
        "whey protein","health drink","weight loss","detox","collagen","multivitamin",
        "omega","ashwagandha","protein bar"]),
    ("ShopsyIOT",["smartwatch","smart band","smart home","alexa","google home",
        "smart lighting","fitness band","wearable","smart switch","smart bulb"]),
    ("ShopsyCamera",["ring light","gimbal","gopro","dslr","camera lens","photography",
        "selfie light","action camera","tripod","vlog setup"]),
    ("ShopsyMensClothingEssentialsAndEthnic",["men kurta","men sherwani","dhoti",
        "men ethnic","bandhgala","nehru jacket","men festive"]),
    ("ShopsyMensClothingCasualTopwear",["men tshirt","men shirt","polo shirt","men hoodie",
        "men sweatshirt","men jacket","men casual","men fashion","men outfit","men wear"]),
    ("ShopsyFoodAndNutrition",["healthy snack","oats","muesli","honey","ghee","dry fruits",
        "nuts","seeds","superfood","health food","organic food"]),
    ("ShopsyHouseHoldSupplies",["detergent","washing powder","dishwash","floor cleaner",
        "toilet cleaner","insect repellent","garbage bag","fabric softener","disinfectant"]),
]
VERTICAL={
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
                return cat,VERTICAL.get(cat,"Other")
    return "Unclassified","Other"

# ── DATA ──────────────────────────────────────────────────────────────────────
BASE_TAGS=["tiktokmademebuyit","instamademebuyit","musthave","viralproduct","justdropped",
    "newarrivals","trendingproducts","unboxing","productreview","triedandtested",
    "meeshofashion","meeshofinds","indianfashion","amazonshopping","onlineshopping",
    "shopthelook","kurtidesign","ethnicwear","makeuptutorial","skincareroutine",
    "hairtransformation","fitnessmotivation","gadgetreview","techunboxing",
    "homedecorinspo","kitchenhacks","meeshohaul","flipkartfinds"]
DATA_FILE="social_trends_data.json"
TRENDS_FILE="trends_history.json"

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

def load_trends_history():
    if not os.path.exists(TRENDS_FILE): return []
    try: return json.load(open(TRENDS_FILE))
    except: return []

def save_trends_snapshot(items):
    history=load_trends_history()
    history.append({"fetched_at":datetime.now().isoformat(),"items":items})
    # keep last 90 days of hourly snapshots (~2160 items)
    json.dump(history[-2160:],open(TRENDS_FILE,"w"),ensure_ascii=False,indent=2)

# ── GOOGLE TRENDS ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800)
def fetch_trends_live():
    try:
        r=_req.get("https://trends.google.com/trending/rss?geo=IN",timeout=8)
        items=re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>",r.text)
        traffic=re.findall(r"<hn:approx_traffic>(.+?)</hn:approx_traffic>",r.text)
        result=[{"topic":t.strip(),"vol":traffic[i].replace("+","") if i<len(traffic) else "",
                 "fetched_at":datetime.now().isoformat()}
                for i,t in enumerate(items[:20]) if t.strip()]
        if result:
            save_trends_snapshot(result)
        return result
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

async def make_base_ctx(pw):
    """Browser context with NO IG cookies — returns public content."""
    args=["--disable-blink-features=AutomationControlled","--no-sandbox","--disable-gpu",
          "--ignore-certificate-errors","--disable-dev-shm-usage","--disable-setuid-sandbox",
          "--no-zygote","--mute-audio"]
    try: browser=await pw.chromium.launch(headless=True,args=args)
    except:
        args.append("--single-process")
        browser=await pw.chromium.launch(headless=True,args=args)
    ctx=await browser.new_context(
        viewport={"width":1280,"height":900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        extra_http_headers={"Accept-Language":"en-IN,en;q=0.9,hi;q=0.8"})
    await ctx.add_init_script("""
        Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
        Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3]});
        window.chrome={runtime:{}};
    """)
    return browser,ctx

async def scrape_ig(ctx, tag, limit=15):
    """
    NO cookies → public hashtag feed, not your personal feed.
    Open explore/tags/{tag} → collect reel URLs → open each reel for og:description.
    og:description = "1.2M views · @creator: caption" — fully public.
    """
    rows=[]; reel_urls=[]
    page=await ctx.new_page()
    try:
        await page.goto(f"https://www.instagram.com/explore/tags/{tag}/",
            wait_until="domcontentloaded",timeout=25000)
        await asyncio.sleep(4)
        if "login" in page.url or "accounts" in page.url:
            # Login wall without cookies — IG blocks this tag publicly
            return rows
        for _ in range(4):
            await page.evaluate("window.scrollBy(0,1200)")
            await asyncio.sleep(0.7)
        links=await page.locator("a[href*='/reel/'],a[href*='/p/']").all()
        for el in links[:limit]:
            href=await el.get_attribute("href")
            if href: reel_urls.append(fu("https://www.instagram.com",href))
    except: pass
    finally:
        try: await page.close()
        except: pass

    # Open each reel page for metadata
    for url in reel_urls[:limit]:
        rp=await ctx.new_page()
        views=likes=creator=thumb=desc_text=posted_on=None; title=""
        try:
            await rp.goto(url,wait_until="domcontentloaded",timeout=18000)
            await asyncio.sleep(1)
            html=await rp.content()

            # og:description: "1.2M views · @username: caption..."
            for pat in [
                r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']*)["\']',
                r'og:description[^>]*content="([^"]*)"',
            ]:
                m=re.search(pat,html,re.I)
                if m:
                    d=m.group(1)
                    vm=re.search(r"([\d,\.]+(?:[\s\u00a0]+(?:crore|lakh))?[KMB]?)\s*(?:views?|plays?)",d,re.I)
                    if vm: views=pn(vm.group(1).strip())
                    lm=re.search(r"([\d,\.]+[KMB]?)\s*likes?",d,re.I)
                    if lm: likes=pn(lm.group(1).strip())
                    cap=re.search(r"@[\w\.]+:\s*(.{5,})",d,re.S)
                    if cap: desc_text=cap.group(1).strip()[:200]
                    break

            # JSON fallbacks
            if not views:
                for pat in [r'"viewCount"\s*:\s*"?([\d,]+)"?',r'"video_view_count"\s*:\s*(\d+)',r'"play_count"\s*:\s*(\d+)']:
                    m=re.search(pat,html)
                    if m: views=pn(m.group(1)); break
            if not likes:
                m=re.search(r'"like_count"\s*:\s*(\d+)',html)
                if m: likes=int(m.group(1))

            # Creator (public JSON in page)
            m=re.search(r'"username"\s*:\s*"([^"]{2,30})"',html)
            if m: creator="@"+m.group(1)

            # Posted on (timestamp)
            m=re.search(r'"taken_at"\s*:\s*(\d+)',html)
            if not m: m=re.search(r'"taken_at_timestamp"\s*:\s*(\d+)',html)
            if m:
                try: posted_on=datetime.fromtimestamp(int(m.group(1))).isoformat()
                except: pass

            # Title from <title> — strip (N) notification, strip " · Instagram"
            m=re.search(r"<title>([^<]+)</title>",html,re.I)
            if m:
                t=m.group(1)
                t=re.sub(r"^\(\d+\)\s*","",t)
                t=re.sub(r"\s*[•·|]\s*Instagram.*$","",t,flags=re.I).strip()
                if len(t)>5: title=t[:200]

            # Thumbnail
            for pat in [
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                r'og:image[^>]*content="([^"]*)"',
            ]:
                m=re.search(pat,html,re.I)
                if m: thumb=m.group(1); break
            if not thumb:
                m=re.search(r'"display_url"\s*:\s*"([^"]+)"',html)
                if m: thumb=m.group(1).replace("\\u0026","&")

        except: pass
        finally:
            try: await rp.close()
            except: pass

        if not title: title=f"#{tag} reel"
        # Classify on title + description + hashtag for better accuracy
        cat,vert=classify(f"{title} {desc_text or ''} {tag}")
        rows.append({
            "platform":"Instagram","content_type":"Reel",
            "hashtag":f"#{tag}","url":url,
            "title":title,"description":desc_text or "",
            "creator":creator or "","thumbnail":thumb or "",
            "posted_on":posted_on or "",
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
            # Posted on from metadata spans — convert relative to absolute datetime
            posted_on=""
            for span in await v.query_selector_all("#metadata-line span"):
                st2=(await span.inner_text()).strip()
                m2=re.search(r"(\d+)\s*(second|minute|hour|day|week|month|year)s?\s*ago",st2,re.I)
                if m2:
                    n2=int(m2.group(1)); unit=m2.group(2).lower()
                    delta_map={"second":1,"minute":60,"hour":3600,"day":86400,
                               "week":604800,"month":2592000,"year":31536000}
                    secs=n2*delta_map.get(unit,86400)
                    approx=datetime.now()-timedelta(seconds=secs)
                    posted_on=approx.isoformat()
                    break
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
            cat,vert=classify(f"{title} {tag}")
            rows.append({
                "platform":"YouTube","content_type":"Shorts" if is_s else "Video",
                "hashtag":f"#{tag}","url":fu("https://www.youtube.com",href),
                "title":title,"description":"","creator":channel,
                "thumbnail":thumb,"vid_id":vid_id,
                "posted_on":posted_on,
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

async def _run_all(hashtags,platforms,per_tag,progress_cb):
    from playwright.async_api import async_playwright
    all_records=[]; BATCH=3
    async with async_playwright() as pw:
        total=len(hashtags); done=0
        for i in range(0,total,BATCH):
            batch=hashtags[i:i+BATCH]
            results=await asyncio.gather(*[_scrape_one(pw,t,platforms,per_tag) for t in batch],
                                         return_exceptions=True)
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
    ctx=await browser.new_context(
        viewport={"width":1280,"height":800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        extra_http_headers={"Accept-Language":"en-IN,en;q=0.9"})
    await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
    # NO IG COOKIES — prevents personal feed contamination
    try:
        if "Instagram" in platforms:
            try:
                ig=await scrape_ig(ctx,tag,per_tag)
                rows.extend(ig)
            except: pass
        if "YouTube" in platforms:
            try:
                yt=await scrape_yt(ctx,tag,per_tag)
                rows.extend(yt)
            except: pass
    finally:
        try: await ctx.close(); await browser.close()
        except: pass
    return rows

def run_sync(hashtags,platforms,per_tag,cb=None):
    result={}; exc=[]; ps={"f":0,"m":"Starting..."}
    def _p(f,m): ps["f"]=f; ps["m"]=m
    def _t():
        loop=asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        try: result["r"]=loop.run_until_complete(_run_all(hashtags,platforms,per_tag,_p))
        except Exception as e: exc.append(e)
        finally: loop.close()
    t=threading.Thread(target=_t,daemon=True); t.start()
    while t.is_alive():
        if cb:
            try: cb(ps["f"],ps["m"])
            except: pass
        time.sleep(1)
    t.join(timeout=10)
    if exc: raise exc[0]
    return result.get("r",[])

# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "init" not in st.session_state:
    st.session_state.init=True
    st.session_state.sel_tags=BASE_TAGS[:10]
    st.session_state.sel_plats=["Instagram","YouTube"]
    st.session_state.per_tag=10
    st.session_state.playing=None   # card_id currently playing

# ── STYLES ────────────────────────────────────────────────────────────────────
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
*{font-family:'Inter',sans-serif!important;}
.block-container{padding:1.2rem 2rem!important;max-width:1400px!important;}
.hero{background:linear-gradient(135deg,#0f172a,#312e81);border-radius:12px;padding:20px 28px;margin-bottom:14px;}
.hero-t{font-size:20px;font-weight:700;color:#f8fafc;}
.hero-s{font-size:11px;color:#a5b4fc;}
.cw{border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.09);background:#fff;margin-bottom:6px;}
.tb{position:relative;background:#111;}
.tb img{width:100%;height:145px;object-fit:cover;display:block;}
.pi{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:36px;height:36px;background:rgba(0,0,0,.62);border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-size:13px;pointer-events:none;}
.st{position:absolute;top:5px;right:5px;background:#c53030;color:#fff;padding:1px 5px;border-radius:3px;font-size:8px;font-weight:700;}
.cb{padding:7px 9px 9px;}
.ct{font-size:11.5px;font-weight:600;color:#1e293b;line-height:1.3;margin:2px 0;}
.cd{font-size:10px;color:#64748b;line-height:1.25;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin-bottom:2px;}
.cm{font-size:10.5px;color:#64748b;margin:1px 0;}
.pb{display:inline-block;padding:1px 5px;border-radius:4px;font-size:8.5px;font-weight:700;color:#fff;margin-right:2px;}
.ca{display:inline-block;padding:2px 7px;border-radius:11px;font-size:9.5px;background:#f0f4ff;color:#4361ee;margin-top:3px;}
.tc{display:inline-block;background:#f0f4ff;color:#4361ee;padding:3px 9px;border-radius:18px;font-size:10.5px;margin:2px;font-weight:500;}
.tv{font-size:9px;color:#94a3b8;margin-left:2px;}
</style>""",unsafe_allow_html=True)

st.markdown('<div class="hero"><div class="hero-t">📱 Social Trend Tracker · Shopsy</div>'
            '<div class="hero-s">Instagram + YouTube · 26 Shopsy Categories · Zero personal data</div></div>',
            unsafe_allow_html=True)

# ── SIDEBAR (sticky) ──────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Settings")
    new_t=st.multiselect("Hashtags",BASE_TAGS,default=st.session_state.sel_tags,key="tp")
    if new_t!=st.session_state.sel_tags: st.session_state.sel_tags=new_t
    custom=st.text_input("+ Custom tag",placeholder="kurtilovers")
    if custom:
        tag=custom.lower().strip("#").replace(" ","")
        if tag and tag not in st.session_state.sel_tags:
            if tag not in BASE_TAGS: BASE_TAGS.append(tag)
            st.session_state.sel_tags=st.session_state.sel_tags+[tag]
            st.rerun()
    new_p=st.multiselect("Platforms",["Instagram","YouTube"],default=st.session_state.sel_plats,key="pp")
    if new_p!=st.session_state.sel_plats: st.session_state.sel_plats=new_p
    new_n=st.slider("Posts/hashtag",5,20,st.session_state.per_tag,key="pn")
    if new_n!=st.session_state.per_tag: st.session_state.per_tag=new_n
    st.divider()
    scrape_btn=st.button("🚀 Scrape",type="primary",use_container_width=True)
    st.divider()
    all_db=load_data()
    st.metric("Stored",len(all_db))
    tags_in_db=sorted({r.get("hashtag","").lstrip("#") for r in all_db if r.get("hashtag")})
    if tags_in_db: st.caption("In DB: "+", ".join(tags_in_db[:6])+("..." if len(tags_in_db)>6 else ""))
    if st.button("🗑 Clear data",use_container_width=True):
        save_data([]); st.rerun()

sel_tags=st.session_state.sel_tags
sel_plats=st.session_state.sel_plats
per_n=st.session_state.per_tag

# ── SCRAPE ─────────────────────────────────────────────────────────────────────
if scrape_btn and sel_tags:
    prog=st.progress(0,"Starting...")
    status=st.empty()
    def cb(f,m):
        try: prog.progress(min(f,0.99),m); status.info(m)
        except: pass
    try:
        new_recs=run_sync(sel_tags,sel_plats,per_n,cb)
        save_data(load_data()+new_recs)
        prog.empty(); status.empty()
        ig_n=sum(1 for r in new_recs if r.get("platform")=="Instagram")
        yt_n=sum(1 for r in new_recs if r.get("platform")=="YouTube")
        st.success(f"✅ Scraped {len(new_recs)} posts  (IG:{ig_n} YT:{yt_n})  for {', '.join('#'+t for t in sel_tags)}")
        st.rerun()
    except Exception as e:
        import traceback; st.error(str(e)); st.code(traceback.format_exc())

# ── LOAD DATA & FILTER TO SELECTED TAGS ───────────────────────────────────────
all_data=load_data()
sel_ht={f"#{t}" for t in sel_tags}

trends_live=fetch_trends_live()

if not all_data:
    if trends_live:
        st.markdown("#### 🔥 Google Trends India")
        st.markdown(" ".join(f'<span class="tc">{t["topic"]}<span class="tv">{t["vol"]}</span></span>' for t in trends_live),unsafe_allow_html=True)
    st.info("No data. Select hashtags → Scrape."); st.stop()

df=pd.DataFrame(all_data)
df["scraped_at"]=pd.to_datetime(df["scraped_at"],errors="coerce")
df["engagement"]=pd.to_numeric(df.get("engagement",0),errors="coerce").fillna(0)
df["views"]=pd.to_numeric(df.get("views",None),errors="coerce")
df["likes"]=pd.to_numeric(df.get("likes",None),errors="coerce")
if "hashtag" not in df.columns: df["hashtag"]=""
if "vertical" not in df.columns: df["vertical"]="Other"
if "content_type" not in df.columns: df["content_type"]=""
if "posted_on" not in df.columns: df["posted_on"]=""
# Parse posted_on to datetime for tab filtering (falls back to scraped_at if missing)
df["uploaded_at"]=pd.to_datetime(df["posted_on"],errors="coerce")
df["uploaded_at"]=df["uploaded_at"].fillna(df["scraped_at"])  # fallback
if "vid_id" not in df.columns: df["vid_id"]=""

# Filter to selected hashtags only
df_sel=df[df["hashtag"].isin(sel_ht)].copy()
if df_sel.empty:
    st.warning(f"No data for {', '.join(list(sel_ht)[:4])}. Click Scrape.")
    df_sel=df.copy()
# Ensure uploaded_at is in df_sel
if "uploaded_at" not in df_sel.columns:
    df_sel["uploaded_at"]=pd.to_datetime(df_sel.get("posted_on",""),errors="coerce").fillna(df_sel["scraped_at"])

# ── GLOBAL FILTER BAR (persistent) ───────────────────────────────────────────
st.markdown("---")
fc1,fc2,fc3=st.columns(3)
with fc1:
    pf=st.multiselect("Platform",sorted(df_sel["platform"].unique()),
        default=list(sorted(df_sel["platform"].unique())),key="gfp")
with fc2:
    cat_opts=sorted(df_sel["category"].unique())
    cf=st.multiselect("Category",cat_opts,key="gfc")
with fc3:
    vert_opts=sorted(df_sel["vertical"].unique())
    vf=st.multiselect("Vertical",vert_opts,key="gfv")

dff=df_sel.copy()
if pf: dff=dff[dff["platform"].isin(pf)]
if cf: dff=dff[dff["category"].isin(cf)]
if vf: dff=dff[dff["vertical"].isin(vf)]
if "uploaded_at" not in dff.columns:
    dff["uploaded_at"]=pd.to_datetime(dff.get("posted_on",""),errors="coerce").fillna(dff["scraped_at"])

# Export
csv_b=io.StringIO(); dff.to_csv(csv_b,index=False)
st.download_button("⬇️ Export CSV",csv_b.getvalue(),"trends.csv","text/csv")

if dff.empty: st.info("No data matches filters."); st.stop()

# ── HELPERS ───────────────────────────────────────────────────────────────────
def fv(v):
    if v is None or (isinstance(v,float) and pd.isna(v)): return "—"
    v=int(v)
    if v>=1_000_000: return f"{v/1_000_000:.1f}M"
    if v>=1_000: return f"{v/1_000:.0f}K"
    return str(v)

def render_card(r:dict, card_id:str):
    plat =r.get("platform",""); ctype=r.get("content_type","")
    url  =r.get("url","#") or "#"; thumb=r.get("thumbnail","")
    title=str(r.get("title",""))[:80]; desc=str(r.get("description",""))[:100]
    cat  =str(r.get("category","")).replace("Shopsy","")
    vert =str(r.get("vertical",""))
    ht   =r.get("hashtag",""); views=r.get("views"); likes=r.get("likes")
    eng  =r.get("engagement",0); cr=r.get("creator","")
    vid_id=str(r.get("vid_id","") or "")
    posted=r.get("posted_on","")
    bc   ="#e1306c" if plat=="Instagram" else "#ff0000"
    is_s =ctype=="Shorts"
    is_playing=st.session_state.playing==card_id

    if is_playing:
        if plat=="YouTube" and vid_id:
            st.markdown(
                f'<iframe width="100%" height="175" src="https://www.youtube.com/embed/{vid_id}?autoplay=1" '
                f'frameborder="0" allowfullscreen style="border-radius:8px;display:block;margin-bottom:4px"></iframe>',
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
        if thumb:
            sb='<div class="st">SHORTS</div>' if is_s else ""
            st.markdown(
                f'<div class="tb"><img src="{thumb}" '
                f'onerror="this.parentNode.style.background=\'#f1f5f9\';this.style.display=\'none\'">'
                f'<div class="pi">▶</div>{sb}</div>',
                unsafe_allow_html=True)
        else:
            em="📸" if plat=="Instagram" else "▶"
            bg="#fce7f3" if plat=="Instagram" else "#fee2e2"
            st.markdown(
                f'<div style="height:145px;background:{bg};border-radius:8px 8px 0 0;'
                f'display:flex;align-items:center;justify-content:center;font-size:28px">{em}</div>',
                unsafe_allow_html=True)
        if st.button("▶ Play",key=f"play_{card_id}",use_container_width=True):
            st.session_state.playing=card_id; st.rerun()

    ht_b=f'<span style="background:#e8ecff;color:#4361ee;padding:1px 4px;border-radius:4px;font-size:8.5px">{ht}</span>'
    pb=f'<span class="pb" style="background:{bc}">{plat}</span>'
    if is_s: pb+=f'<span class="pb" style="background:#c53030">SHORTS</span>'
    metric="  ·  ".join(filter(None,[
        f"👁 {fv(views)}" if views and not pd.isna(views) else None,
        f"❤️ {fv(likes)}" if likes and not pd.isna(likes) else None,
    ])) or f"Eng: {fv(eng)}"
    posted_line=f'<div class="cm">🕐 {posted}</div>' if posted else ""
    cat_v=f'{cat}{" · "+vert if vert and vert!="Other" else ""}'
    st.markdown(f"""<div class="cb">
<div>{pb} {ht_b}</div>
<div class="ct">{title}</div>
{"<div class='cd'>"+desc+"</div>" if desc else ""}
{"<div class='cm'>👤 "+cr+"</div>" if cr else ""}
{posted_line}
<div class="cm">{metric}</div>
<div class="ca">🏷 {cat_v}</div>
</div>""",unsafe_allow_html=True)
    st.link_button("Open ↗",url,use_container_width=True)

def render_grid(data:pd.DataFrame, label:str, max_n:int=50):
    if data.empty:
        st.info("No posts in this time window for selected hashtags."); return
    c1,c2,c3=st.columns(3)
    with c1: srt=st.selectbox("Sort",["Engagement","Views","Recent"],key=f"s_{label}")
    with c2: pp=st.selectbox("Platform",["All","Instagram","YouTube"],key=f"p_{label}")
    with c3: cp=st.selectbox("Category",["All"]+sorted(data["category"].unique().tolist()),key=f"c_{label}")
    d=data.copy()
    if pp!="All": d=d[d["platform"]==pp]
    if cp!="All": d=d[d["category"]==cp]
    if srt=="Engagement": d=d.sort_values("engagement",ascending=False)
    elif srt=="Views": d=d.sort_values("views",ascending=False,na_position="last")
    else: d=d.sort_values("scraped_at",ascending=False)
    d=d.head(max_n).reset_index(drop=True)
    tags_shown=sorted({r["hashtag"] for _,r in d.iterrows()})
    st.caption(f"{len(d)} posts · {srt} · tags: {', '.join(tags_shown)}")
    for i in range(0,len(d),4):
        cols=st.columns(4)
        for j,(_,r) in enumerate(d.iloc[i:i+4].iterrows()):
            with cols[j]:
                render_card(r.to_dict(),f"{label}_{i+j}")

# ── TABS ──────────────────────────────────────────────────────────────────────
now=datetime.now()
t_l30,t_l7,t_l1,t_top,t_gt,t_stats=st.tabs([
    "📅 Last 30 Days","📅 Last 7 Days","📅 Last 24h",
    "🏆 Top 20","🔥 Google Trends","📊 Stats"
])

# Time-window data — uses scraped_at (when we scraped it)
# Note: all records scraped in same session will appear in all windows.
# The meaningful difference comes after multiple scrape runs across days.
# We show count + date range to make it clear.
# Filter by when content was actually UPLOADED (not when we scraped it)
d30=dff[dff["uploaded_at"]>=now-timedelta(days=30)]
d7 =dff[dff["uploaded_at"]>=now-timedelta(days=7)]
d1 =dff[dff["uploaded_at"]>=now-timedelta(hours=24)]

with t_l30:
    st.caption(f"Reels/videos uploaded in last 30 days: **{len(d30)}** (of {len(dff)} total)")
    render_grid(d30,"l30",60)

with t_l7:
    st.caption(f"Reels/videos uploaded in last 7 days: **{len(d7)}** (of {len(dff)} total)")
    render_grid(d7,"l7",40)

with t_l1:
    st.caption(f"Reels/videos uploaded in last 24 hours: **{len(d1)}** (of {len(dff)} total)")
    render_grid(d1,"l1d",30)

with t_top:
    st.subheader("🏆 Top 20 by Engagement")
    ic,yc=st.columns(2)
    with ic:
        st.markdown("#### 📸 Instagram")
        ig_t=dff[dff["platform"]=="Instagram"].sort_values("engagement",ascending=False).head(20).reset_index(drop=True)
        if ig_t.empty: st.info("No Instagram data.")
        for i,(_,r) in enumerate(ig_t.iterrows()):
            a,b=st.columns([1,4])
            with a:
                if r.get("thumbnail"): st.image(r["thumbnail"],width=58)
                else: st.markdown('<div style="width:58px;height:58px;background:#fce7f3;border-radius:6px;display:flex;align-items:center;justify-content:center">📸</div>',unsafe_allow_html=True)
            with b:
                v=r.get("views"); l=r.get("likes")
                m2="  ·  ".join(filter(None,[f"👁 {fv(v)}" if v and not pd.isna(v) else None,f"❤️ {fv(l)}" if l and not pd.isna(l) else None])) or "—"
                st.markdown(f"**#{i+1}** {str(r.get('title',''))[:55]}")
                st.caption(f"{m2}  ·  {r.get('creator','')}  ·  {r.get('hashtag','')}")
                if r.get("posted_on"): st.caption(f"🕐 {r['posted_on']}")
                st.caption(f"🏷 {str(r.get('category','')).replace('Shopsy','')}")
                st.link_button("View →",r.get("url","#"),key=f"tig_{i}")
            st.markdown("<hr style='margin:2px 0;border:none;border-top:1px solid #f1f5f9'>",unsafe_allow_html=True)
    with yc:
        st.markdown("#### ▶ YouTube")
        yt_t=dff[dff["platform"]=="YouTube"].sort_values("engagement",ascending=False).head(20).reset_index(drop=True)
        if yt_t.empty: st.info("No YouTube data.")
        for i,(_,r) in enumerate(yt_t.iterrows()):
            a,b=st.columns([1,4])
            with a:
                if r.get("thumbnail"): st.image(r["thumbnail"],width=58)
                else: st.markdown('<div style="width:58px;height:58px;background:#fee2e2;border-radius:6px;display:flex;align-items:center;justify-content:center">▶</div>',unsafe_allow_html=True)
            with b:
                ct=str(r.get("content_type","Video"))
                sb=f'<span style="background:#c53030;color:#fff;padding:1px 4px;border-radius:3px;font-size:8px">{ct}</span> ' if ct=="Shorts" else ""
                st.markdown(f"**#{i+1}** {sb}{str(r.get('title',''))[:55]}",unsafe_allow_html=True)
                st.caption(f"👁 {fv(r.get('views'))}  ·  {r.get('creator','')}  ·  {r.get('hashtag','')}")
                if r.get("posted_on"): st.caption(f"🕐 {r['posted_on']}")
                st.caption(f"🏷 {str(r.get('category','')).replace('Shopsy','')}")
                st.link_button("Watch →",r.get("url","#"),key=f"tyt_{i}")
            st.markdown("<hr style='margin:2px 0;border:none;border-top:1px solid #f1f5f9'>",unsafe_allow_html=True)

with t_gt:
    st.subheader("🔥 Google Trends India")
    st.caption("Refreshes every 30 minutes · Stored across sessions for L30/L7/L1 history")

    # Live now
    if trends_live:
        st.markdown("##### Live Right Now")
        chips=" ".join(f'<span class="tc">{t["topic"]}<span class="tv"> {t["vol"]}/day</span></span>' for t in trends_live)
        st.markdown(chips,unsafe_allow_html=True)
        st.divider()

    # Historical from stored snapshots
    history=load_trends_history()
    if history:
        h_df=pd.DataFrame([
            {"topic":item["topic"],"vol":item.get("vol",""),
             "fetched_at":pd.to_datetime(snap["fetched_at"])}
            for snap in history for item in snap.get("items",[])
        ])
        h_df["fetched_at"]=pd.to_datetime(h_df["fetched_at"],errors="coerce")

        gt1,gt2,gt3=st.tabs(["Last 30 Days","Last 7 Days","Last 24h"])
        for tab,days,lbl in [(gt1,30,"L30"),(gt2,7,"L7"),(gt3,1,"L1")]:
            with tab:
                cutoff=now-timedelta(days=days)
                sub=h_df[h_df["fetched_at"]>=cutoff]
                if sub.empty:
                    st.info(f"No trend history for {lbl} yet — check back after more scrapes.")
                else:
                    # Most frequent trending topics in this window
                    freq=sub.groupby("topic").size().reset_index(name="appearances").sort_values("appearances",ascending=False)
                    st.markdown(f"**{len(freq)} unique trending topics** in this window")
                    for _,row in freq.head(30).iterrows():
                        st.markdown(f'<span class="tc">{row["topic"]}<span class="tv"> {row["appearances"]}x</span></span>',unsafe_allow_html=True)
    else:
        st.info("Trend history builds up over time as the app is used. Come back after a few scrapes!")

with t_stats:
    st.subheader("📊 Stats")
    m1,m2,m3,m4=st.columns(4)
    with m1: st.metric("Posts",len(dff))
    with m2: st.metric("Instagram",len(dff[dff["platform"]=="Instagram"]))
    with m3: st.metric("YouTube",len(dff[dff["platform"]=="YouTube"]))
    with m4: st.metric("Categories",dff["category"].nunique())
    st.divider()
    ch1,ch2=st.columns(2)
    with ch1:
        st.markdown("#### Top Categories")
        cc=dff["category"].value_counts().head(15).reset_index()
        cc.columns=["Category","Count"]
        cc["Category"]=cc["Category"].str.replace("Shopsy","")
        st.bar_chart(cc.set_index("Category")["Count"])
    with ch2:
        st.markdown("#### Vertical Engagement")
        ve=dff.groupby("vertical")["engagement"].sum().sort_values(ascending=False).reset_index()
        st.bar_chart(ve.set_index("vertical")["engagement"])
    st.divider()
    yt2=dff[dff["platform"]=="YouTube"]
    if not yt2.empty and "content_type" in yt2.columns:
        ct2=yt2["content_type"].value_counts().reset_index(); ct2.columns=["Type","Count"]
        st.markdown("#### YouTube Types")
        st.bar_chart(ct2.set_index("Type")["Count"])
    st.divider()
    st.markdown("#### Hashtag Performance")
    hs=dff.groupby("hashtag").agg(Posts=("url","count"),TotalEng=("engagement","sum"),AvgEng=("engagement","mean")).round(0).sort_values("TotalEng",ascending=False).reset_index()
    st.dataframe(hs,use_container_width=True)
    st.divider()
    st.markdown("#### Full Data")
    display_cols=[c for c in ["platform","content_type","hashtag","title","creator","views","likes","engagement","category","vertical","posted_on","url"] if c in dff.columns]
    st.dataframe(dff[display_cols],use_container_width=True,height=350)
