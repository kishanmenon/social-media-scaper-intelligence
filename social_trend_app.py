"""
social_trend_app.py \u2014 Final
============================
- IG + YouTube reels/videos with thumbnails + in-app playback
- Shopsy category classification (26 categories)
- L30/L7/Today tabs + Lifetime Top 20
- Google Trends live chips
- YouTube Shorts detection
- No personal data exposure
"""

import streamlit as st
import asyncio, sys, os, re, json, threading, subprocess, time
from datetime import datetime, timedelta
from urllib.parse import quote
import pandas as pd
import requests

st.set_page_config(page_title="Trend Tracker \u00b7 Shopsy", page_icon="\ud83d\udcf1", layout="wide")

@st.cache_resource
def install_chromium():
    try:
        subprocess.run([sys.executable,"-m","playwright","install","chromium"],
                      capture_output=True, text=True, timeout=120)
        return "ok"
    except: return "failed"
_ch = install_chromium()

def get_secret(key, default=""):
    try: return st.secrets.get(key, default) or default
    except: return os.environ.get(key, default)

IG_SESSIONID  = get_secret("IG_SESSIONID")
IG_CSRFTOKEN  = get_secret("IG_CSRFTOKEN")
IG_DS_USER_ID = get_secret("IG_DS_USER_ID")

# \u2500\u2500 CATEGORY CLASSIFIER \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# analytic_category \u2192 keywords to detect from reel title/caption
CATEGORIES = [
    ("ShopsyWomenEthnicContemporary", ["kurti","kurta","saree","sari","lehenga","salwar",
        "dupatta","anarkali","ethnic","palazzo","patiala","gharara","sharara","churidar",
        "cotton kurti","printed kurti","silk saree","banarasi","kalamkari"]),
    ("ShopsyWomenWesternCore", ["crop top","co-ord","coord set","bodycon","midi dress",
        "maxi dress","women top","women shirt","women dress","women skirt","women jeans",
        "women trouser","women jacket","women blazer","women sweatshirt","women hoodie"]),
    ("ShopsyMakeupFragrances", ["lipstick","lip gloss","lip liner","foundation","concealer",
        "mascara","eyeliner","eyeshadow","blush","highlighter","kajal","makeup","nail polish",
        "perfume","mehendi","sindoor","bindi","compact","primer","contour","bronzer"]),
    ("ShopsyGrooming", ["shampoo","conditioner","hair oil","face wash","moisturizer","serum",
        "sunscreen","body wash","scrub","toner","skincare","skin care","facewash","lotion",
        "face cream","body lotion","hair mask","hair serum","vitamin c","niacinamide",
        "retinol","hyaluronic","micellar","cleansing oil","face mist"]),
    ("ShopsyPersonalHealthCare", ["trimmer","hair dryer","straightener","curler","epilator",
        "massager","weighing scale","bp monitor","thermometer","glucometer","nebulizer",
        "hair styler","shaver","electric toothbrush","water flosser","facial steamer"]),
    ("ShopsyAudio", ["earphone","earbuds","headphone","speaker","bluetooth speaker",
        "tws","airpods","neckband","soundbar","wired earphone","gaming headset",
        "noise cancelling","anc headphone","true wireless"]),
    ("ShopsyMobileProtection", ["phone case","back cover","screen guard","tempered glass",
        "mobile cover","phone cover","case cover","mobile protection","camera protector"]),
    ("ShopsyRestOfMobileAccessory", ["charger","charging cable","power bank","mobile holder",
        "selfie stick","data cable","fast charger","usb cable","type c","wireless charger",
        "phone stand","mobile stand"]),
    ("ShopsyHomeDecor", ["candle","diya","pooja","wall decor","showpiece","wall clock","vase",
        "painting","fairy lights","led strip","home decor","artificial flower","idol","lamp",
        "wall hanging","dream catcher","photo frame","decorative","home aesthetic"]),
    ("ShopsyHouseHold", ["pressure cooker","kadhai","tawa","container","lunch box",
        "water bottle","flask","cookware","utensil","chopper","kitchen","non stick",
        "casserole","dinner set","steel utensil","kitchen tool"]),
    ("ShopsyHomeFurnishing", ["bedsheet","pillow","curtain","blanket","towel","mattress",
        "cushion cover","table cover","carpet","rug","bath mat","bed cover","duvet","quilt"]),
    ("ShopsySportFitness", ["yoga mat","dumbbell","resistance band","gym","fitness","cricket",
        "badminton","football","cycling","workout","exercise","skipping rope","gym bag",
        "gym wear","sports","ab roller","protein shaker"]),
    ("ShopsyKidClothing", ["kids wear","children","baby clothes","boy shirt","girl dress",
        "infant","kids tshirt","kids kurta","kids jacket","school uniform","baby outfit",
        "kids fashion"]),
    ("ShopsyToysAndSS", ["toy","puzzle","board game","pen","notebook","stationery","crayon",
        "art kit","learning toy","rc toy","stuffed toy","lego","craft","playdoh","slime",
        "fidget","pop it"]),
    ("ShopsyBabyCare", ["baby","diaper","baby food","baby oil","baby shampoo","baby soap",
        "stroller","feeding bottle","baby care","infant care","baby powder","teether",
        "baby lotion","baby product"]),
    ("ShopsyLuggageAndTravelAccessories", ["handbag","backpack","sling bag","tote","travel bag",
        "suitcase","purse","wallet","clutch","laptop bag","school bag","duffle","college bag",
        "office bag","women bag"]),
    ("ShopsyFashionWearables", ["jewellery","jewelry","earring","necklace","bracelet","ring",
        "bangle","watch","sunglasses","belt","chain","pendant","anklet","mangalsutra",
        "maang tikka","fashion accessories"]),
    ("ShopsyFootwear", ["shoes","sandals","heels","sneakers","boots","slippers","chappal",
        "footwear","loafers","flip flops","sports shoes","formal shoes","wedges","bellies",
        "jutti","mojari"]),
    ("ShopsyCoreEA", ["mixer grinder","juicer","iron box","kettle","toaster","induction cooktop",
        "roti maker","sandwich maker","air fryer","electric cooker","hand blender",
        "electric iron","food processor"]),
    ("ShopsyHealthCare", ["protein","vitamin","supplement","ayurvedic","immunity booster",
        "probiotic","whey protein","health drink","weight loss","detox","collagen",
        "multivitamin","omega","ashwagandha","chyawanprash","protein bar"]),
    ("ShopsyIOT", ["smartwatch","smart band","smart home","alexa","google home",
        "smart lighting","fitness band","wearable","smart switch","smart bulb","iot device"]),
    ("ShopsyCamera", ["camera","tripod","ring light","gimbal","vlog camera","gopro","dslr",
        "camera lens","photography","selfie light","action camera","camera setup"]),
    ("ShopsyMensClothingEssentialsAndEthnic", ["men kurta","men sherwani","dhoti",
        "men ethnic","lungi","bandhgala","nehru jacket","men ethnic wear","men festive wear"]),
    ("ShopsyMensClothingCasualTopwear", ["men tshirt","men shirt","polo shirt","men hoodie",
        "men sweatshirt","men jacket","men casual","men fashion","men outfit","men style",
        "men wear"]),
    ("ShopsyFoodAndNutrition", ["food","snack","chocolate","tea","coffee","dry fruits",
        "spices","healthy food","oats","muesli","honey","ghee","masala","nuts","seeds",
        "superfood","healthy snack"]),
    ("ShopsyHouseHoldSupplies", ["detergent","washing powder","dishwash","floor cleaner",
        "toilet cleaner","insect repellent","garbage bag","fabric softener","disinfectant",
        "cleaning product"]),
]

VERTICAL_MAP = {
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
    "ShopsySportFitness":"Sports","ShopsyToysAndSS":"Toys & Stationery",
    "ShopsyFoodAndNutrition":"Food",
}

def classify(text: str):
    if not text: return "Unclassified", "Other"
    text_lower = text.lower()
    for cat, keywords in CATEGORIES:
        for kw in keywords:
            if kw in text_lower:
                return cat, VERTICAL_MAP.get(cat,"Other")
    return "Unclassified", "Other"

# \u2500\u2500 HASHTAGS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
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
        try: tags += json.load(open(DISCOVER_FILE)).get("tags",[])
        except: pass
    return list(dict.fromkeys(tags))

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

# \u2500\u2500 SCRAPER \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
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

async def make_ctx(pw):
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
        Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});
        window.chrome={runtime:{}};
    """)
    # Inject IG cookies ONLY for auth bypass \u2014 not to personalise feed
    ig_c=[]
    if IG_SESSIONID: ig_c.append({"name":"sessionid","value":IG_SESSIONID,"domain":".instagram.com","path":"/","httpOnly":True,"secure":True,"sameSite":"Lax"})
    if IG_CSRFTOKEN: ig_c.append({"name":"csrftoken","value":IG_CSRFTOKEN,"domain":".instagram.com","path":"/","secure":True,"sameSite":"Lax"})
    if ig_c: await ctx.add_cookies(ig_c)
    return browser,ctx

async def scrape_ig_tag(ctx, tag, limit=15):
    rows=[]; reel_urls=[]
    page=await ctx.new_page()
    try:
        await page.goto(f"https://www.instagram.com/explore/tags/{tag}/",
            wait_until="domcontentloaded",timeout=25000)
        await asyncio.sleep(4)
        if "login" in page.url or "accounts" in page.url:
            return rows
        for _ in range(4):
            await page.evaluate("window.scrollBy(0,1200)")
            await asyncio.sleep(0.8)
        for el in (await page.locator("a[href*='/reel/'],a[href*='/p/']").all())[:limit]:
            href=await el.get_attribute("href")
            if not href: continue
            img_el=el.locator("img").first
            alt=(await img_el.get_attribute("alt") if await img_el.count() else "") or ""
            reel_urls.append((alt[:150], fmt_url("https://www.instagram.com",href)))
    except: pass
    finally:
        try: await page.close()
        except: pass

    for alt,url in reel_urls[:limit]:
        rp=await ctx.new_page()
        views=likes=creator=thumb=description=None; title=alt
        try:
            await rp.goto(url,wait_until="domcontentloaded",timeout=18000)
            await asyncio.sleep(1)
            html=await rp.content()

            # og:description: "1.2M views \u00b7 @username: caption text here"
            og=re.search(r'og:description[^>]*content="([^"]*)"',html,re.I)
            if og:
                desc_text=og.group(1)
                vm=re.search(r"([\d,\.]+(?:[\s\u00a0]+(?:crore|lakh))?[KMB]?)\s*(?:views?|plays?)",desc_text,re.I)
                if vm: views=parse_num(vm.group(1).strip())
                lm=re.search(r"([\d,\.]+[KMB]?)\s*likes?",desc_text,re.I)
                if lm: likes=parse_num(lm.group(1).strip())
                # Extract caption (after the colon following @username)
                cap=re.search(r"@[\w\.]+:\s*(.+)",desc_text,re.S)
                if cap: description=cap.group(1).strip()[:300]

            # JSON fallbacks for views
            if not views:
                for pat in [r'"viewCount"\s*:\s*"?([\d,]+)"?',r'"video_view_count"\s*:\s*(\d+)',r'"play_count"\s*:\s*(\d+)']:
                    jv=re.search(pat,html)
                    if jv: views=parse_num(jv.group(1)); break
            if not likes:
                jl=re.search(r'"like_count"\s*:\s*(\d+)',html)
                if jl: likes=int(jl.group(1))

            # Creator \u2014 from JSON, not from personalized feed
            cr=re.search(r'"username"\s*:\s*"([^"]+)"',html)
            if cr: creator="@"+cr.group(1)

            # Real title from page <title>
            t_tag=re.search(r"<title>([^<]+)</title>",html,re.I)
            if t_tag:
                t=re.sub(r"\s*[\u2022\u00b7|]\s*Instagram.*$","",t_tag.group(1),flags=re.I).strip()
                if len(t)>5: title=t[:200]

            # Thumbnail from og:image
            og_img=re.search(r'og:image[^>]*content="([^"]*)"',html,re.I)
            if og_img: thumb=og_img.group(1)

            # Also try JSON for better thumbnail
            jthumb=re.search(r'"display_url"\s*:\s*"([^"]+)"',html)
            if jthumb and not thumb: thumb=jthumb.group(1).replace("\\u0026","&")

        except: pass
        finally:
            try: await rp.close()
            except: pass

        cat,vert=classify(title+" "+(description or ""))
        rows.append({
            "platform":"Instagram","content_type":"Reel",
            "hashtag":f"#{tag}","url":url,
            "title":title,"description":description or "",
            "creator":creator or "","thumbnail":thumb or "",
            "views":views,"likes":likes,"engagement":views or likes or 0,
            "category":cat,"vertical":vert,
            "scraped_at":datetime.now().isoformat(),
        })
    rows.sort(key=lambda x:x.get("engagement") or 0,reverse=True)
    return rows

async def scrape_yt_tag(ctx, tag, limit=25):
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
                if vm: views=parse_num(vm.group(1).strip()); break
            if not views:
                aria=await t_el.get_attribute("aria-label") or ""
                vm2=re.search(r"([\d,\.]+[KMB]?)\s*views?",aria,re.I)
                if vm2: views=parse_num(vm2.group(1))
            ch_el=await v.query_selector("#channel-name a,ytd-channel-name a")
            channel=(await ch_el.inner_text()).strip() if ch_el else ""
            href=await t_el.get_attribute("href") or ""
            # Detect Shorts
            is_short = "/shorts/" in href
            vid_m=re.search(r"(?:v=|/shorts/)([A-Za-z0-9_-]{11})",href)
            thumb=f"https://img.youtube.com/vi/{vid_m.group(1)}/mqdefault.jpg" if vid_m else ""
            vid_id=vid_m.group(1) if vid_m else ""
            # Duration from aria-label for shorts detection
            if not is_short:
                dur_el=await v.query_selector("span.ytd-thumbnail-overlay-time-status-renderer")
                if dur_el:
                    dur=(await dur_el.inner_text()).strip()
                    # Shorts \u2264 60 sec
                    dm=re.match(r"^(\d+):(\d+)$",dur)
                    if dm and int(dm.group(1))==0: is_short=True
            content_type="Shorts" if is_short else "Video"
            cat,vert=classify(title)
            rows.append({
                "platform":"YouTube","content_type":content_type,
                "hashtag":f"#{tag}","url":fmt_url("https://www.youtube.com",href),
                "title":title,"description":"",
                "creator":channel,"thumbnail":thumb,"vid_id":vid_id,
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
    BATCH=3
    async with async_playwright() as pw:
        # Get trending tags first
        browser0,ctx0=await make_ctx(pw)
        try: discovered=await get_trending_tags(ctx0)
        except: pass
        finally:
            try: await ctx0.close(); await browser0.close()
            except: pass

        total=len(hashtags); done=0
        for batch_start in range(0,total,BATCH):
            batch=hashtags[batch_start:batch_start+BATCH]
            tasks=[]
            for tag in batch:
                tasks.append(_scrape_tag(pw,tag,platforms,per_tag))
            results=await asyncio.gather(*tasks,return_exceptions=True)
            for r in results:
                if isinstance(r,list): all_records.extend(r)
            done+=len(batch)
            if progress_cb: progress_cb(done/total,f"Done {done}/{total} hashtags")
    return all_records,discovered

async def _scrape_tag(pw,tag,platforms,per_tag):
    from playwright.async_api import async_playwright
    rows=[]
    args=["--disable-blink-features=AutomationControlled","--no-sandbox","--disable-gpu",
          "--ignore-certificate-errors","--disable-dev-shm-usage","--disable-setuid-sandbox",
          "--no-zygote","--mute-audio"]
    try:
        browser=await pw.chromium.launch(headless=True,args=args)
    except:
        args.append("--single-process")
        browser=await pw.chromium.launch(headless=True,args=args)
    ctx=await browser.new_context(
        viewport={"width":1280,"height":800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        extra_http_headers={"Accept-Language":"en-IN,en;q=0.9"})
    await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
    ig_c=[]
    if IG_SESSIONID: ig_c.append({"name":"sessionid","value":IG_SESSIONID,"domain":".instagram.com","path":"/","httpOnly":True,"secure":True,"sameSite":"Lax"})
    if IG_CSRFTOKEN: ig_c.append({"name":"csrftoken","value":IG_CSRFTOKEN,"domain":".instagram.com","path":"/","secure":True,"sameSite":"Lax"})
    if ig_c: await ctx.add_cookies(ig_c)
    try:
        if "Instagram" in platforms:
            try: rows.extend(await scrape_ig_tag(ctx,tag,per_tag))
            except: pass
        if "YouTube" in platforms:
            try: rows.extend(await scrape_yt_tag(ctx,tag,per_tag))
            except: pass
    finally:
        try: await ctx.close(); await browser.close()
        except: pass
    return rows

def run_sync(hashtags,platforms,per_tag,progress_cb=None):
    result={}; exc=[]; progress_state={"frac":0,"msg":"Starting..."}
    def _p(frac,msg): progress_state["frac"]=frac; progress_state["msg"]=msg
    def _t():
        loop=asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        try: result["r"]=loop.run_until_complete(_run_all(hashtags,platforms,per_tag,_p))
        except Exception as e: exc.append(e)
        finally: loop.close()
    t=threading.Thread(target=_t,daemon=True); t.start()
    while t.is_alive():
        if progress_cb:
            try: progress_cb(progress_state["frac"],progress_state["msg"])
            except: pass
        time.sleep(1)
    t.join(timeout=10)
    if exc: raise exc[0]
    return result.get("r",([],[]))

# \u2500\u2500 GOOGLE TRENDS (no browser needed) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
@st.cache_data(ttl=1800)  # cache 30 min
def fetch_google_trends():
    try:
        r=requests.get("https://trends.google.com/trending/rss?geo=IN",timeout=8)
        items=re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>",r.text)
        traffic=re.findall(r"<hn:approx_traffic>(.+?)</hn:approx_traffic>",r.text)
        result=[]
        for i,t in enumerate(items[:20]):
            vol=traffic[i].replace("+","") if i<len(traffic) else ""
            result.append({"topic":t.strip(),"volume":vol})
        return result
    except: return []

# \u2500\u2500 STYLES \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
*{font-family:'Inter',sans-serif;}
.block-container{padding:1.5rem 2rem;max-width:1400px;}
.hero{background:linear-gradient(135deg,#0f172a,#312e81);border-radius:14px;padding:28px 36px;margin-bottom:20px;}
.hero-title{font-size:24px;font-weight:700;color:#f8fafc;}
.hero-sub{font-size:13px;color:#a5b4fc;margin-top:4px;}
.card{background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);margin-bottom:8px;}
.card-body{padding:10px 12px 12px;}
.card-title{font-size:12.5px;font-weight:600;color:#1e293b;line-height:1.4;margin-bottom:4px;}
.card-desc{font-size:11px;color:#64748b;line-height:1.4;margin-bottom:4px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
.card-meta{font-size:11px;color:#64748b;margin-top:2px;}
.badge{display:inline-block;padding:2px 7px;border-radius:8px;font-size:10px;font-weight:700;color:#fff;margin-right:4px;}
.cat-badge{display:inline-block;padding:2px 7px;border-radius:8px;font-size:10px;background:#f0f4ff;color:#4361ee;margin-top:4px;}
.trend-chip{display:inline-block;background:#f0f4ff;color:#4361ee;padding:4px 11px;border-radius:20px;font-size:11px;margin:2px;font-weight:500;}
.trend-chip-vol{font-size:10px;color:#94a3b8;margin-left:3px;}
.thumb-wrap{position:relative;width:100%;background:#000;}
.thumb-wrap img{width:100%;height:160px;object-fit:cover;display:block;}
.play-overlay{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:44px;height:44px;background:rgba(0,0,0,.6);border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer;}
.shorts-badge{position:absolute;top:6px;right:6px;background:#ff0000;color:#fff;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:700;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <div class="hero-title">\ud83d\udcf1 Social Trend Tracker \u00b7 Shopsy</div>
  <div class="hero-sub">Instagram Reels + YouTube Videos/Shorts \u00b7 Shopsy Category Classification \u00b7 L30 / L7 / Today + Lifetime Top 20</div>
</div>""", unsafe_allow_html=True)

# Cookie status
has_ig = bool(IG_SESSIONID)
st.markdown(
    f'<span style="background:{"#22c55e" if has_ig else "#f59e0b"};color:#fff;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600">{"\u2705 IG cookies active" if has_ig else "\u26a0\ufe0f IG cookies not set \u2014 add in Secrets"}</span>',
    unsafe_allow_html=True)

# \u2500\u2500 SIDEBAR \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
with st.sidebar:
    st.title("\u2699\ufe0f Settings")
    all_tags=load_all_hashtags()
    selected=st.multiselect("Hashtags",options=all_tags,default=all_tags[:12])
    custom=st.text_input("+ Add hashtag",placeholder="e.g. kurtilovers")
    if custom:
        tag=custom.lower().strip("#").replace(" ","")
        if tag and tag not in selected: selected.append(tag)
    platforms=st.multiselect("Platforms",["Instagram","YouTube"],default=["Instagram","YouTube"])
    per_tag=st.slider("Posts per hashtag",5,25,12)
    st.divider()
    scrape_btn=st.button("\ud83d\ude80 Scrape Now",type="primary",use_container_width=True)
    st.divider()
    existing=load_data()
    st.metric("Stored records",len(existing))
    if existing:
        last=max(r.get("scraped_at","") for r in existing)
        st.caption(f"Last: {last[:16]}")
    if st.button("\ud83d\uddd1 Clear data",use_container_width=True):
        save_data([]); st.rerun()

# \u2500\u2500 SCRAPE \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
if scrape_btn and selected:
    prog=st.progress(0,"Starting...")
    status=st.empty()
    def cb(frac,msg):
        try: prog.progress(min(frac,0.99),msg); status.info(msg)
        except: pass
    try:
        new_records,discovered=run_sync(selected,platforms,per_tag,cb)
        existing=load_data()
        save_data(existing+new_records)
        prog.empty(); status.empty()
        st.success(f"\u2705 {len(new_records)} new posts scraped.")
        if discovered:
            json.dump({"tags":discovered,"updated":datetime.now().isoformat()},
                      open(DISCOVER_FILE,"w"))
        st.rerun()
    except Exception as e:
        import traceback
        st.error(f"Error: {e}"); st.code(traceback.format_exc())

# \u2500\u2500 LOAD DATA \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
all_data=load_data()
if not all_data:
    # Show Google Trends even with no scraped data
    trends=fetch_google_trends()
    if trends:
        st.markdown("#### \ud83d\udd25 Google Trending India Right Now")
        chips=" ".join(f'<span class="trend-chip">{t["topic"]}<span class="trend-chip-vol">{t["volume"]}</span></span>' for t in trends)
        st.markdown(chips,unsafe_allow_html=True)
    st.info("No data yet. Click **Scrape Now** to fetch content.")
    st.stop()

df=pd.DataFrame(all_data)
df["scraped_at"]=pd.to_datetime(df["scraped_at"],errors="coerce")
df["engagement"]=pd.to_numeric(df.get("engagement",0),errors="coerce").fillna(0)
df["views"]=pd.to_numeric(df.get("views",None),errors="coerce")
df["likes"]=pd.to_numeric(df.get("likes",None),errors="coerce")

# Global filters
fc1,fc2,fc3,fc4=st.columns(4)
with fc1: pf=st.multiselect("Platform",["Instagram","YouTube"],default=["Instagram","YouTube"],key="gf_p")
with fc2: ctf=st.multiselect("Content type",["Reel","Video","Shorts"],default=["Reel","Video","Shorts"],key="gf_ct")
with fc3: cf=st.multiselect("Category",sorted(df["category"].unique().tolist()),key="gf_c")
with fc4: vf=st.multiselect("Vertical",sorted(df["vertical"].unique().tolist()) if "vertical" in df.columns else [],key="gf_v")

if pf: df=df[df["platform"].isin(pf)]
if ctf and "content_type" in df.columns: df=df[df["content_type"].isin(ctf)]
if cf: df=df[df["category"].isin(cf)]
if vf and "vertical" in df.columns: df=df[df["vertical"].isin(vf)]
if df.empty: st.info("No data matches filters."); st.stop()

# \u2500\u2500 HELPERS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def fv(v):
    if not v or pd.isna(v): return "\u2014"
    v=int(v)
    if v>=1_000_000: return f"{v/1_000_000:.1f}M"
    if v>=1_000: return f"{v/1_000:.0f}K"
    return str(v)

def render_card(r: dict, card_id: str):
    """Render a single content card with thumbnail, play button, metadata."""
    plat   = r.get("platform","")
    ctype  = r.get("content_type","")
    url    = r.get("url","#") or "#"
    thumb  = r.get("thumbnail","")
    title  = str(r.get("title",""))[:90]
    desc   = str(r.get("description",""))[:120]
    cat    = str(r.get("category","")).replace("Shopsy","")
    vert   = str(r.get("vertical",""))
    ht     = r.get("hashtag","")
    views  = r.get("views")
    likes  = r.get("likes")
    eng    = r.get("engagement",0)
    cr     = r.get("creator","")
    vid_id = r.get("vid_id","")
    col_b  = "#e1306c" if plat=="Instagram" else "#ff0000"
    is_short = ctype=="Shorts"

    show_key = f"show_{card_id}"

    # Thumbnail with play overlay
    if st.session_state.get(show_key, False):
        # Show embedded player
        if plat=="YouTube" and vid_id:
            embed_url = f"https://www.youtube.com/embed/{vid_id}?autoplay=1"
            st.markdown(f'<iframe width="100%" height="200" src="{embed_url}" frameborder="0" allowfullscreen style="border-radius:8px"></iframe>', unsafe_allow_html=True)
        elif plat=="Instagram":
            clean=url.split("?")[0].rstrip("/")
            st.markdown(f'<blockquote class="instagram-media" data-instgrm-permalink="{url}" data-instgrm-version="14" style="width:100%!important;min-width:180px;border-radius:8px"></blockquote><script async src="//www.instagram.com/embed.js"></script>', unsafe_allow_html=True)
        if st.button("\u2715 Close", key=f"close_{card_id}", use_container_width=True):
            st.session_state[show_key] = False
            st.rerun()
    else:
        # Show thumbnail
        thumb_html = ""
        if thumb:
            short_badge = '<span class="shorts-badge">SHORTS</span>' if is_short else ""
            thumb_html = f'''<div class="thumb-wrap" style="position:relative">
  <img src="{thumb}" onerror="this.src='https://via.placeholder.com/320x180/f1f5f9/94a3b8?text=No+Image'" style="width:100%;height:160px;object-fit:cover;border-radius:8px 8px 0 0">
  <div class="play-overlay">\u25b6</div>
  {short_badge}
</div>'''
        else:
            thumb_html = f'<div style="height:160px;background:{"#fce7f3" if plat=="Instagram" else "#fee2e2"};border-radius:8px 8px 0 0;display:flex;align-items:center;justify-content:center;font-size:36px">{"\ud83d\udcf8" if plat=="Instagram" else "\u25b6"}</div>'
        st.markdown(thumb_html, unsafe_allow_html=True)
        if st.button("\u25b6 Play", key=f"play_{card_id}", use_container_width=True):
            st.session_state[show_key] = True
            st.rerun()

    # Card body
    badges = f'<span class="badge" style="background:{col_b}">{plat}</span>'
    if is_short: badges += '<span class="badge" style="background:#ff0000">Shorts</span>'
    badges += f'<span style="background:#e8ecff;color:#4361ee;padding:2px 6px;border-radius:8px;font-size:10px">{ht}</span>'

    metric = "  \u00b7  ".join(filter(None,[
        f"\ud83d\udc41 {fv(views)}" if views and not pd.isna(views) else None,
        f"\u2764\ufe0f {fv(likes)}" if likes and not pd.isna(likes) else None,
    ])) or f"Eng: {fv(eng)}"

    st.markdown(f"""<div class="card-body">
  <div style="margin-bottom:4px">{badges}</div>
  <div class="card-title">{title}</div>
  {"<div class='card-desc'>"+desc+"</div>" if desc else ""}
  <div class="card-meta">{"\ud83d\udc64 "+cr if cr else ""}</div>
  <div class="card-meta">{metric}</div>
  <div class="cat-badge">\ud83c\udff7 {cat} {"\u00b7 "+vert if vert and vert!="Other" else ""}</div>
</div>""", unsafe_allow_html=True)
    st.link_button("Open \u2197", url, use_container_width=True)

def render_grid(data: pd.DataFrame, max_items: int, label: str):
    if data.empty: st.info("No posts."); return
    c1,c2,c3=st.columns(3)
    with c1: s=st.selectbox("Sort",["Engagement","Views","Recent"],key=f"s_{label}")
    with c2: p=st.selectbox("Platform",["All","Instagram","YouTube"],key=f"p_{label}")
    with c3: c=st.selectbox("Category",["All"]+sorted(data["category"].unique().tolist()),key=f"c_{label}")
    d=data.copy()
    if p!="All": d=d[d["platform"]==p]
    if c!="All": d=d[d["category"]==c]
    if s=="Engagement": d=d.sort_values("engagement",ascending=False)
    elif s=="Views": d=d.sort_values("views",ascending=False,na_position="last")
    elif s=="Recent": d=d.sort_values("scraped_at",ascending=False)
    d=d.head(max_items).reset_index(drop=True)
    st.caption(f"{len(d)} posts \u00b7 sort: {s}")
    for i in range(0,len(d),4):
        cols=st.columns(4)
        for j,(_,r) in enumerate(d.iloc[i:i+4].iterrows()):
            with cols[j]:
                render_card(r.to_dict(), f"{label}_{i+j}")

# \u2500\u2500 TABS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
now=datetime.now()
t30,t7,tod,top20,stats=st.tabs([
    "\ud83d\udcc5 Last 30 Days","\ud83d\udcc5 Last 7 Days","\ud83d\udcc5 Today/Yesterday",
    "\ud83c\udfc6 Lifetime Top 20","\ud83d\udcca Stats & Trends"
])
with t30:
    render_grid(df[df["scraped_at"]>=now-timedelta(days=30)],60,"l30")
with t7:
    render_grid(df[df["scraped_at"]>=now-timedelta(days=7)],40,"l7")
with tod:
    render_grid(df[df["scraped_at"]>=now-timedelta(days=2)],30,"today")

with top20:
    st.subheader("\ud83c\udfc6 Lifetime Top 20")
    ig_c,yt_c=st.columns(2)
    with ig_c:
        st.markdown("#### \ud83d\udcf8 Instagram")
        ig_top=df[df["platform"]=="Instagram"].sort_values("engagement",ascending=False).head(20).reset_index(drop=True)
        for i,(_,r) in enumerate(ig_top.iterrows()):
            c1,c2=st.columns([1,4])
            with c1:
                thumb=r.get("thumbnail","")
                if thumb: st.image(thumb,width=65)
                else: st.markdown('<div style="width:65px;height:65px;background:#fce7f3;border-radius:8px;display:flex;align-items:center;justify-content:center">\ud83d\udcf8</div>',unsafe_allow_html=True)
            with c2:
                views=r.get("views"); likes=r.get("likes")
                m="  \u00b7  ".join(filter(None,[f"\ud83d\udc41 {fv(views)}" if views and not pd.isna(views) else None,f"\u2764\ufe0f {fv(likes)}" if likes and not pd.isna(likes) else None])) or f"Eng: {fv(r.get('engagement'))}"
                st.markdown(f"**#{i+1}** {str(r.get('title',''))[:60]}")
                st.caption(f"{m}  \u00b7  {r.get('creator','')}  \u00b7  {r.get('hashtag','')}")
                st.caption(f"\ud83c\udff7 {str(r.get('category','')).replace('Shopsy','')}")
                st.link_button("View \u2192",r.get("url","#"),key=f"top_ig_{i}")
            st.markdown("<hr style='margin:3px 0;border:none;border-top:1px solid #f1f5f9'>",unsafe_allow_html=True)

    with yt_c:
        st.markdown("#### \u25b6 YouTube")
        yt_top=df[df["platform"]=="YouTube"].sort_values("engagement",ascending=False).head(20).reset_index(drop=True)
        for i,(_,r) in enumerate(yt_top.iterrows()):
            c1,c2=st.columns([1,4])
            with c1:
                thumb=r.get("thumbnail","")
                if thumb: st.image(thumb,width=65)
                else: st.markdown('<div style="width:65px;height:65px;background:#fee2e2;border-radius:8px;display:flex;align-items:center;justify-content:center">\u25b6</div>',unsafe_allow_html=True)
            with c2:
                ctype=str(r.get("content_type","Video"))
                badge=f'<span style="background:#ff0000;color:#fff;padding:1px 5px;border-radius:4px;font-size:9px;font-weight:700">{ctype}</span> ' if ctype=="Shorts" else ""
                st.markdown(f"**#{i+1}** {badge}{str(r.get('title',''))[:60]}",unsafe_allow_html=True)
                st.caption(f"\ud83d\udc41 {fv(r.get('views'))}  \u00b7  {r.get('creator','')}  \u00b7  {r.get('hashtag','')}")
                st.caption(f"\ud83c\udff7 {str(r.get('category','')).replace('Shopsy','')}")
                st.link_button("Watch \u2192",r.get("url","#"),key=f"top_yt_{i}")
            st.markdown("<hr style='margin:3px 0;border:none;border-top:1px solid #f1f5f9'>",unsafe_allow_html=True)

with stats:
    st.subheader("\ud83d\udcca Stats & Trends")

    # Google Trends \u2014 live, no scraping needed
    trends=fetch_google_trends()
    if trends:
        st.markdown("#### \ud83d\udd25 Google Trending India Right Now")
        chips=" ".join(
            f'<span class="trend-chip">{t["topic"]}<span class="trend-chip-vol"> {t["volume"]}</span></span>'
            for t in trends)
        st.markdown(chips,unsafe_allow_html=True)
        st.divider()

    m1,m2,m3,m4=st.columns(4)
    with m1: st.metric("Total Posts",len(df))
    with m2: st.metric("Instagram",len(df[df["platform"]=="Instagram"]))
    with m3: st.metric("YouTube",len(df[df["platform"]=="YouTube"]))
    with m4: st.metric("Categories",df["category"].nunique())
    st.divider()

    ch1,ch2=st.columns(2)
    with ch1:
        st.markdown("#### Top Categories (post count)")
        cc=df["category"].value_counts().head(15).reset_index()
        cc.columns=["Category","Count"]
        cc["Category"]=cc["Category"].str.replace("Shopsy","")
        st.bar_chart(cc.set_index("Category")["Count"])
    with ch2:
        st.markdown("#### Vertical Engagement")
        if "vertical" in df.columns:
            ve=df.groupby("vertical")["engagement"].sum().sort_values(ascending=False).reset_index()
            ve.columns=["Vertical","Engagement"]
            st.bar_chart(ve.set_index("Vertical")["Engagement"])

    if "content_type" in df.columns:
        st.divider()
        st.markdown("#### YouTube: Videos vs Shorts")
        yt_df=df[df["platform"]=="YouTube"]
        if not yt_df.empty:
            ct=yt_df["content_type"].value_counts().reset_index()
            ct.columns=["Type","Count"]
            st.bar_chart(ct.set_index("Type")["Count"])

    st.divider()
    st.markdown("#### Category Breakdown")
    cs=df.groupby(["category","platform"]).agg(Posts=("url","count"),AvgEng=("engagement","mean"),TotalEng=("engagement","sum")).round(0).reset_index().sort_values("TotalEng",ascending=False)
    cs["category"]=cs["category"].str.replace("Shopsy","")
    st.dataframe(cs,use_container_width=True,height=350)

    st.divider()
    st.markdown("#### Hashtag Performance")
    hs=df.groupby("hashtag").agg(Posts=("url","count"),TotalEng=("engagement","sum"),AvgEng=("engagement","mean")).round(0).sort_values("TotalEng",ascending=False).reset_index()
    st.dataframe(hs,use_container_width=True)
