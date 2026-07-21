"""
social_trend_app.py v10
Key fixes based on scrape_reels_to_excel.py:
- Completely removed "Vertical" UI filters and old category dictionaries.
- Integrated exact _BU_RULES regex classification from reference code.
- Integrated exact og:description regex parsing for IG views/likes.
- Added strict <time> and article:published_time regex for accurate IG dates.
- Enforced no-referrer policy for thumbnails.
"""
import streamlit as st
import asyncio, sys, os, re, json, threading, subprocess, time, io
from datetime import datetime, timedelta
import pandas as pd
import requests as _req

st.set_page_config(page_title="Trend Tracker · BU Classification", page_icon="📱", layout="wide")

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

# ── BU CLASSIFIER (From Reference Code) ───────────────────────────────────────
_BU_RULES = [
    ("Not A Product Video", re.compile(
        r"\b(news|politics|cricket|football|movie|song|music|dance|comedy|"
        r"meme|travel vlog|festival|wedding|birthday|baby shower|graduation|"
        r"motivation|finance|stock|crypto|recipe|cook|chef)\b", re.I)),
    ("Electronics", re.compile(
        r"\b(phone|mobile|laptop|tablet|ipad|iphone|samsung|redmi|oneplus|"
        r"realme|vivo|oppo|headphone|earphone|earbuds|speaker|charger|cable|"
        r"powerbank|power bank|camera|smartwatch|smart watch|led|tv|television|"
        r"router|wifi|keyboard|mouse|monitor|printer|gadget|electronics)\b", re.I)),
    ("BPC", re.compile(
        r"\b(skincare|skin care|serum|moisturizer|sunscreen|spf|face wash|"
        r"facewash|toner|foundation|lipstick|lip gloss|mascara|eyeliner|"
        r"blush|concealer|makeup|beauty|perfume|deodorant|shampoo|conditioner|"
        r"hair oil|hair care|haircare|nail|bpc|cosmetic|lotion|cream|"
        r"face pack|face mask|vitamin c|retinol|niacinamide|hyaluronic)\b", re.I)),
    ("Women+Kids Apparel", re.compile(
        r"\b(kurti|kurta|saree|sari|lehenga|salwar|dupatta|anarkali|"
        r"ethnic wear|ethnic|women.s wear|ladies|girls|kids wear|children.s|"
        r"baby clothes|frock|dress|blouse|women top|tunics|palazzo)\b", re.I)),
    ("Men Apparel", re.compile(
        r"\b(men.s wear|mens|shirt|kurta for men|sherwani|men.s shirt|"
        r"men.s jacket|men.s jeans|men.s tshirt|t-shirt|polo|hoodie|"
        r"sweatshirt|blazer|trousers|chinos|men.s fashion)\b", re.I)),
    ("Footwear", re.compile(
        r"\b(shoes|sneakers|sandals|heels|boots|footwear|slippers|loafers|"
        r"flip flop|chappal|nike|adidas|puma|woodland|bata)\b", re.I)),
    ("Travel & Accessory", re.compile(
        r"\b(bag|handbag|purse|wallet|clutch|backpack|luggage|suitcase|"
        r"trolley bag|travel bag|tote|shoulder bag|belt|watch|sunglasses|"
        r"jewellery|jewelry|earring|necklace|ring|bracelet|accessory|accessories)\b", re.I)),
    ("Home", re.compile(
        r"\b(home decor|home decoration|bedsheet|pillow|curtain|sofa|"
        r"kitchen|cookware|utensil|container|storage|organizer|lamp|"
        r"candle|frame|mirror|carpet|rug|mat|cushion|bedding|towel|"
        r"dining|tableware|crockery|wall art|home)\b", re.I)),
    ("Furniture", re.compile(
        r"\b(furniture|chair|table|desk|bed frame|wardrobe|shelf|bookshelf|"
        r"cabinet|sofa set|couch|recliner|study table|office chair)\b", re.I)),
    ("HAT", re.compile(
        r"\b(hat|cap|beanie|helmet|headband|hair accessory|scrunchie|"
        r"hair clip|hair band|turban)\b", re.I)),
    ("GM", re.compile(
        r"\b(toy|game|puzzle|stationery|pen|notebook|craft|art supply|"
        r"sports|gym|fitness|yoga mat|dumbbell|cycle|bicycle|scooter|"
        r"outdoor|camping|gardening|tools|hardware)\b", re.I)),
    ("Large", re.compile(
        r"\b(washing machine|refrigerator|fridge|ac |air conditioner|"
        r"microwave|oven|dishwasher|water purifier|geyser|air purifier|"
        r"vacuum cleaner|mixer grinder|blender|juicer|induction|large appliance)\b", re.I)),
]

def classify_bu(title: str) -> str:
    if not title: return "Other"
    for bu, pat in _BU_RULES:
        if pat.search(title): return bu
    return "Other"

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

# ── PARSERS (From Reference Code) ──────────────────────────────────────────────
def parse_num(s):
    if not s: return None
    s = str(s).strip()
    for pat, mul in [
        (r"([\d.]+)\s*crore", 10_000_000),
        (r"([\d.]+)\s*lakh",  100_000),
        (r"([\d.]+)\s*thousand", 1_000),
    ]:
        m = re.search(pat, s, re.I)
        if m:
            try: return int(float(m.group(1)) * mul)
            except: pass
    s2 = s.upper().replace(",","").replace("(","").replace(")","")
    m = re.search(r"([\d.]+)\s*([KMB]?)", s2)
    if not m: return None
    try:
        n = float(m.group(1))
        return int(n * {"K":1000,"M":1_000_000,"B":1_000_000_000}.get(m.group(2),1))
    except: return None

def fmt(domain, link):
    if not link: return ""
    link = link.strip()
    if link.startswith("http"): return link
    return f"{domain}{link}" if link.startswith("/") else f"{domain}/{link}"

# ── SCRAPERS ──────────────────────────────────────────────────────────────────
async def scrape_ig(ctx, tag, limit=15):
    rows=[]
    reel_urls=[]; page=await ctx.new_page()
    try:
        await page.goto(f"https://www.instagram.com/explore/tags/{tag}/", wait_until="domcontentloaded", timeout=25000)
        await asyncio.sleep(4)
        if "login" in page.url or "accounts" in page.url:
            return rows

        # Click recent tab
        for recent_sel in ["span:text-is('Recent')", "div[role='tab']:has-text('Recent')", "a[href*='recent']"]:
            try:
                tab=page.locator(recent_sel).first
                if await tab.count():
                    await tab.click()
                    await asyncio.sleep(2.5)
                    break
            except: continue

        for _ in range(5):
            await page.evaluate("window.scrollBy(0,1500)")
            await asyncio.sleep(0.8)
            
        links=await page.locator("a[href*='/reel/'],a[href*='/p/']").all()
        seen_u=set()
        for el in links[:limit*2]:
            href=await el.get_attribute("href")
            if href and href not in seen_u:
                seen_u.add(href)
                reel_urls.append(fmt("https://www.instagram.com",href))
    except: pass
    finally:
        try: await page.close()
        except: pass

    # Open each reel page - using exact reference code regex strategy
    for url in reel_urls[:limit]:
        rp=await ctx.new_page()
        views=likes=creator=thumb=desc_text=posted_on=None
        title=""
        try:
            await rp.goto(url, wait_until="domcontentloaded", timeout=18000)
            await asyncio.sleep(2) 
            html=await rp.content()

            # Views/Likes using Reference Code logic
            og = re.search(r'og:description[^>]*content="([^"]*)"', html, re.I)
            if og:
                desc = og.group(1)
                vm = re.search(r"([\d,\.]+(?:[\s\u00a0]+(?:crore|lakh))?[KMB]?)\s*(?:views?|plays?)", desc, re.I)
                if vm: views = parse_num(vm.group(1).strip())
                lm = re.search(r"([\d,\.]+[KMB]?)\s*likes?", desc, re.I)
                if lm: likes = parse_num(lm.group(1).strip())
                
                # Extract creator and description from og tag
                cap = re.search(r"(@[\w\.]+):\s*(.{5,})", desc, re.S)
                if cap:
                    creator = cap.group(1)
                    desc_text = cap.group(2).strip()[:200]

            # Title extraction using Reference Code logic
            t_tag = re.search(r"<title>([^<]+)</title>", html, re.I)
            if t_tag:
                t = re.sub(r"\s*[•·|]\s*Instagram.*$", "", t_tag.group(1)).strip()
                if len(t) > 5: title = t[:200]

            # Accurate Date Extraction (missing from reference script, explicitly added for time tabs)
            time_m = re.search(r'<time[^>]+datetime="([^"]+)"', html, re.I)
            if time_m:
                posted_on = time_m.group(1)
            if not posted_on:
                ts_m = re.search(r'<meta\s+property="article:published_time"\s+content="([^"]+)"', html, re.I)
                if ts_m: posted_on = ts_m.group(1)

            # Thumbnail fallback
            img_m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html, re.I)
            if img_m: thumb = img_m.group(1).replace("&amp;", "&")

        except: pass
        finally:
            try: await rp.close()
            except: pass

        if not title: title=f"#{tag} reel"
        
        # BU Classification utilizing title + description
        bu_cat = classify_bu(f"{title} {desc_text or ''} {tag}")
        
        rows.append({
            "platform":"Instagram", "content_type":"Reel",
            "hashtag":f"#{tag}", "url":url, "title":title.replace('\n', ' '),
            "description":desc_text.replace('\n', ' ') if desc_text else "", "creator":creator or "", "thumbnail":thumb or "",
            "posted_on":posted_on or "", "views":views, "likes":likes,
            "engagement":views or likes or 0, "category":bu_cat,
            "scraped_at":datetime.now().isoformat(),
        })

    rows.sort(key=lambda x:x.get("posted_on","") or "", reverse=True)
    return rows[:limit]

async def scrape_yt(ctx, tag, limit=25):
    rows=[]; page=await ctx.new_page()
    try:
        await page.goto(f"https://www.youtube.com/results?search_query=%23{tag}&sp=CAI%3D", wait_until="domcontentloaded", timeout=25000)
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
            
            # Views extraction using Reference Code logic
            views=None
            for span in await v.query_selector_all("#metadata-line span"):
                st2=(await span.inner_text()).strip()
                vm=re.search(r"([\d,\.]+(?:[\s\u00a0]+(?:crore|lakh))?[KMB]?)\s*views?", st2, re.I)
                if vm: views = parse_num(vm.group(1).strip()); break
            if not views:
                aria = await t_el.get_attribute("aria-label") or ""
                vm2 = re.search(r"([\d,\.]+(?:[\s\u00a0]+(?:crore|lakh))?[KMB]?)\s*views?", aria, re.I)
                if vm2: views = parse_num(vm2.group(1).strip())
            
            # Date extraction
            posted_on=""
            for span in await v.query_selector_all("#metadata-line span"):
                st2=(await span.inner_text()).strip()
                m2=re.search(r"(\d+)\s*(second|minute|hour|day|week|month|year)s?\s*ago", st2, re.I)
                if m2:
                    n2=int(m2.group(1)); unit=m2.group(2).lower()
                    delta_map={"second":1,"minute":60,"hour":3600,"day":86400, "week":604800,"month":2592000,"year":31536000}
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
            
            bu_cat = classify_bu(f"{title} {tag}")
            
            rows.append({
                "platform":"YouTube", "content_type":"Shorts" if is_s else "Video",
                "hashtag":f"#{tag}", "url":fmt("https://www.youtube.com",href),
                "title":title, "description":"", "creator":channel,
                "thumbnail":thumb, "vid_id":vid_id,
                "posted_on":posted_on, "views":views, "likes":None,
                "engagement":views or 0, "category":bu_cat,
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
            results=await asyncio.gather(*[_scrape_one(pw,t,platforms,per_tag) for t in batch], return_exceptions=True)
            for r in results:
                if isinstance(r,list): all_records.extend(r)
            done+=len(batch)
            if progress_cb: progress_cb(done/total,f"{done}/{total} hashtags")
    return all_records

async def _scrape_one(pw,tag,platforms,per_tag):
    rows=[]
    args=["--disable-blink-features=AutomationControlled","--no-sandbox","--disable-gpu",
          "--ignore-certificate-errors","--disable-dev-shm-usage","--disable-setuid-sandbox", "--no-zygote","--mute-audio"]
    try: browser=await pw.chromium.launch(headless=True,args=args)
    except:
        args.append("--single-process")
        browser=await pw.chromium.launch(headless=True,args=args)
    ctx=await browser.new_context(
        viewport={"width":1280,"height":800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        extra_http_headers={"Accept-Language":"en-IN,en;q=0.9"})
    await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
    cks=[]
    if IG_SESSIONID: cks.append({"name":"sessionid","value":IG_SESSIONID,"domain":".instagram.com","path":"/","httpOnly":True,"secure":True,"sameSite":"Lax"})
    if IG_CSRFTOKEN: cks.append({"name":"csrftoken","value":IG_CSRFTOKEN,"domain":".instagram.com","path":"/","secure":True,"sameSite":"Lax"})
    if cks: await ctx.add_cookies(cks)
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
    st.session_state.sort_mode="Engagement ↓"
    st.session_state.playing=None

# ── STYLES ────────────────────────────────────────────────────────────────────
st.markdown("""
<meta name="referrer" content="no-referrer">
<style>
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

st.markdown('<div class="hero"><div class="hero-t">📱 Social Trend Tracker · BU Categories</div>'
            '<div class="hero-s">Instagram + YouTube · Auto-classified using BU Rules</div></div>',
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
    new_n=st.slider("Posts per hashtag per platform",5,30,st.session_state.per_tag,key="pn")
    if new_n!=st.session_state.per_tag: st.session_state.per_tag=new_n
    st.divider()
    new_sort=st.radio("Sort / Rank by",
        ["Engagement ↓","Recency × Engagement","Most Recent ↓"],
        index=["Engagement ↓","Recency × Engagement","Most Recent ↓"].index(st.session_state.get("sort_mode","Engagement ↓")),
        key="sort_radio")
    if new_sort!=st.session_state.get("sort_mode"): st.session_state.sort_mode=new_sort
    st.divider()
    scrape_btn=st.button("🚀 Scrape Now",type="primary",use_container_width=True)
    st.divider()
    all_db=load_data()
    st.metric("Stored",len(all_db))
    if st.button("🗑 Clear data",use_container_width=True):
        save_data([]); st.rerun()

sel_tags=st.session_state.sel_tags
sel_plats=st.session_state.sel_plats
per_n=st.session_state.per_tag

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
        st.success(f"✅ Scraped {len(new_recs)} posts  (IG:{ig_n} YT:{yt_n})")
        st.rerun()
    except Exception as e:
        st.error(str(e))

all_data=load_data()
sel_ht={f"#{t}" for t in sel_tags}

if not all_data:
    st.info("No data. Select hashtags → Scrape."); st.stop()

df=pd.DataFrame(all_data)
df["scraped_at"]=pd.to_datetime(df["scraped_at"],errors="coerce")
df["engagement"]=pd.to_numeric(df.get("engagement",0),errors="coerce").fillna(0)
df["views"]=pd.to_numeric(df.get("views",None),errors="coerce")
df["likes"]=pd.to_numeric(df.get("likes",None),errors="coerce")
if "hashtag" not in df.columns: df["hashtag"]=""
if "category" not in df.columns: df["category"]="Other"
if "content_type" not in df.columns: df["content_type"]=""
if "posted_on" not in df.columns: df["posted_on"]=""
# Accurate extracted date logic for the UI tabs
df["uploaded_at"]=pd.to_datetime(df["posted_on"],errors="coerce")

df_sel=df[df["hashtag"].isin(sel_ht)].copy()
if df_sel.empty: df_sel=df.copy()

# ── VIEW FILTERS (Vertical Completely Removed) ────────────────────────────────
st.markdown("---")
# Single Category filter based on BU Rules
cat_opts=["All"]+sorted(df_sel["category"].unique())
cf_val=st.selectbox("Filter by Category (BU)", cat_opts, key="gfc")

dff=df_sel.copy()
if sel_plats: dff=dff[dff["platform"].isin(sel_plats)]
if cf_val!="All": dff=dff[dff["category"]==cf_val]

csv_b=io.StringIO(); dff.to_csv(csv_b,index=False)
st.download_button("⬇️ Export CSV",csv_b.getvalue(),"trends.csv","text/csv")
if dff.empty: st.info("No data matches filters."); st.stop()

def fv(v):
    if pd.isna(v): return "—"
    v=int(v)
    if v>=1_000_000: return f"{v/1_000_000:.1f}M"
    if v>=1_000: return f"{v/1_000:.0f}K"
    return str(v)

def recency_x_eng(data):
    import numpy as np
    d=data.copy()
    ref_col="uploaded_at" if d["uploaded_at"].notna().any() else "scraped_at"
    ref=pd.to_datetime(d[ref_col],errors="coerce")
    age_days=((pd.Timestamp.now()-ref).dt.total_seconds()/86400).fillna(30).clip(0,365)
    eng=pd.to_numeric(d["engagement"],errors="coerce").fillna(0)
    d["_score"]=eng*np.exp(-age_days/7)
    return d.sort_values("_score",ascending=False).drop(columns=["_score"])

def apply_sort(d):
    srt=st.session_state.get("sort_mode","Engagement ↓")
    if srt=="Engagement ↓": return d.sort_values("engagement",ascending=False)
    elif srt=="Recency × Engagement": return recency_x_eng(d)
    else: return d.sort_values("uploaded_at",ascending=False,na_position="last")

def render_card(r:dict, card_id:str):
    plat =r.get("platform",""); ctype=r.get("content_type","")
    url  =r.get("url","#") or "#"; thumb=r.get("thumbnail","")
    title=str(r.get("title",""))[:80]; desc=str(r.get("description",""))[:100]
    cat  =str(r.get("category",""))
    ht   =r.get("hashtag",""); views=r.get("views"); likes=r.get("likes")
    eng  =r.get("engagement",0); cr=r.get("creator","")
    vid_id=str(r.get("vid_id","") or "")
    posted=r.get("posted_on","")
    bc   ="#e1306c" if plat=="Instagram" else "#ff0000"
    is_s =ctype=="Shorts"
    is_playing=st.session_state.playing==card_id

    if is_playing:
        if plat=="YouTube" and vid_id:
            st.markdown(f'<iframe width="100%" height="175" src="https://www.youtube.com/embed/{vid_id}?autoplay=1" frameborder="0" allowfullscreen style="border-radius:8px;display:block;margin-bottom:4px"></iframe>',unsafe_allow_html=True)
        elif plat=="Instagram":
            st.markdown(f'<blockquote class="instagram-media" data-instgrm-permalink="{url}" data-instgrm-version="14" style="width:100%!important;min-width:180px"></blockquote><script async src="//www.instagram.com/embed.js"></script>',unsafe_allow_html=True)
        if st.button("✕ Close",key=f"cls_{card_id}",use_container_width=True):
            st.session_state.playing=None; st.rerun()
    else:
        if thumb:
            sb='<div class="st">SHORTS</div>' if is_s else ""
            st.markdown(f'<div class="tb"><img src="{thumb}" onerror="this.parentNode.style.background=\'#f1f5f9\';this.style.display=\'none\'"><div class="pi">▶</div>{sb}</div>',unsafe_allow_html=True)
        else:
            em="📸" if plat=="Instagram" else "▶"
            bg="#fce7f3" if plat=="Instagram" else "#fee2e2"
            st.markdown(f'<div style="height:145px;background:{bg};border-radius:8px 8px 0 0;display:flex;align-items:center;justify-content:center;font-size:28px">{em}</div>',unsafe_allow_html=True)
        if st.button("▶ Play",key=f"play_{card_id}",use_container_width=True):
            st.session_state.playing=card_id; st.rerun()

    ht_b=f'<span style="background:#e8ecff;color:#4361ee;padding:1px 4px;border-radius:4px;font-size:8.5px">{ht}</span>'
    pb=f'<span class="pb" style="background:{bc}">{plat}</span>'
    if is_s: pb+=f'<span class="pb" style="background:#c53030">SHORTS</span>'
    metric="  ·  ".join(filter(None,[f"👁 {fv(views)}" if not pd.isna(views) else None, f"❤️ {fv(likes)}" if not pd.isna(likes) else None])) or f"Eng: {fv(eng)}"
    posted_line=f'<div class="cm">🕐 {posted[:10] if posted else ""}</div>' if posted else ""
    st.markdown(f"""<div class="cb"><div>{pb} {ht_b}</div><div class="ct">{title}</div>{"<div class='cd'>"+desc+"</div>" if desc else ""}{"<div class='cm'>👤 "+cr+"</div>" if cr else ""}{posted_line}<div class="cm">{metric}</div><div class="ca">🏷 {cat}</div></div>""",unsafe_allow_html=True)
    st.link_button("Open ↗",url,use_container_width=True)

def render_grid(data, label, max_n=50, ct_filter="All"):
    if data.empty: st.info("No posts for this view."); return
    d=data.copy()
    if ct_filter=="Shorts": d=d[d["content_type"]=="Shorts"]
    elif ct_filter=="Videos": d=d[(d["platform"]=="YouTube")&(d["content_type"]!="Shorts")]
    elif ct_filter=="Instagram": d=d[d["platform"]=="Instagram"]
    elif ct_filter=="YouTube": d=d[d["platform"]=="YouTube"]
    d=apply_sort(d).head(max_n).reset_index(drop=True)
    st.caption(f"**{len(d)} posts** displayed")
    for i in range(0,len(d),4):
        cols=st.columns(4)
        for j,(_,r) in enumerate(d.iloc[i:i+4].iterrows()):
            with cols[j]: render_card(r.to_dict(),f"{label}_{i+j}")

now=datetime.now()
ua=pd.to_datetime(dff["uploaded_at"],errors="coerce")
d30=dff[ua.notna()&(ua>=now-timedelta(days=30))]
d7 =dff[ua.notna()&(ua>=now-timedelta(days=7))]
d1 =dff[ua.notna()&(ua>=now-timedelta(days=1))]

t_l30,t_l7,t_l1,t_all,t_stats=st.tabs([f"📅 L30 Days ({len(d30)})",f"📅 L7 Days ({len(d7)})",f"📅 Last 24h ({len(d1)})",f"🏆 Lifetime ({len(dff)})","📊 Stats"])

with t_l30: render_grid(d30,"l30",60)
with t_l7: render_grid(d7,"l7",40)
with t_l1: render_grid(d1,"l1d",30)
with t_all: render_grid(dff,"life_all",80)

with t_stats:
    st.subheader("📊 Stats")
    m1,m2,m3,m4=st.columns(4)
    with m1: st.metric("Total",len(dff))
    with m2: st.metric("Instagram",len(dff[dff["platform"]=="Instagram"]))
    with m3: st.metric("YouTube",len(dff[dff["platform"]=="YouTube"]))
    with m4: st.metric("Categories",dff["category"].nunique())
