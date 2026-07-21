"""
social_trend_app.py v15 (Direct Script Embed)
Key features:
- Directly embeds the exact logic from scrape_reels_to_excel.py
- Replaced "BU" with "Category" per user constraints.
- Only added cookie injection for the login wall bypass.
- Minimal UI wrapper to choose hashtags, run the exact script, and sort.
"""
import streamlit as st
import asyncio, sys, os, re, json, threading, subprocess, time, io
from datetime import datetime, timedelta
import pandas as pd

st.set_page_config(page_title="Trend Tracker", page_icon="📱", layout="wide")

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

# ── CATEGORY CLASSIFIER (Direct from your _BU_RULES) ──────────────────────────
_CATEGORY_RULES = [
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

def classify_category(title: str) -> str:
    if not title: return "None"
    for cat, pat in _CATEGORY_RULES:
        if pat.search(title): return cat
    return "None"

# ── UTILITIES (Direct from your code) ──────────────────────────────────────────
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

async def scroll(page, n=3, d=1500):
    for _ in range(n):
        await page.evaluate(f"window.scrollBy(0,{d})")
        await asyncio.sleep(0.8)

# ── SCRAPERS (Direct from your code) ───────────────────────────────────────────
async def scrape_ig_tag(ctx, tag, limit=100):
    """Scrapes IG using exact logic from scrape_reels_to_excel.py"""
    rows = []
    page = await ctx.new_page()
    reel_urls = []
    try:
        await page.goto(f"https://www.instagram.com/explore/tags/{tag}/", wait_until="domcontentloaded", timeout=25000)
        await asyncio.sleep(4)
        if "login" in page.url or "accounts" in page.url:
            return rows
        
        await scroll(page, 5, 1200)
        links = await page.locator("a[href*='/reel/'], a[href*='/p/']").all()
        for el in links[:limit]:
            href = await el.get_attribute("href")
            if not href: continue
            img_el = el.locator("img").first
            alt = (await img_el.get_attribute("alt") if await img_el.count() else "") or ""
            thumb = (await img_el.get_attribute("src") if await img_el.count() else "") or ""
            full = fmt("https://www.instagram.com", href)
            reel_urls.append((alt[:200], full, thumb))
    except: pass
    finally:
        try: await page.close()
        except: pass

    for i, (alt, url, thumb) in enumerate(reel_urls[:limit]):
        rp = await ctx.new_page()
        views = likes = None
        title = alt
        try:
            await rp.goto(url, wait_until="domcontentloaded", timeout=18000)
            await asyncio.sleep(1)
            html = await rp.content()
            og = re.search(r'og:description[^>]*content="([^"]*)"', html, re.I)
            if og:
                desc = og.group(1)
                vm = re.search(r"([\d,\.]+(?:[\s\u00a0]+(?:crore|lakh))?[KMB]?)\s*(?:views?|plays?)", desc, re.I)
                if vm: views = parse_num(vm.group(1).strip())
                lm = re.search(r"([\d,\.]+[KMB]?)\s*likes?", desc, re.I)
                if lm: likes = parse_num(lm.group(1).strip())
            t_tag = re.search(r"<title>([^<]+)</title>", html, re.I)
            if t_tag:
                t = re.sub(r"\s*[•·|]\s*Instagram.*$", "", t_tag.group(1)).strip()
                if len(t) > 5: title = t[:200]
        except: pass
        finally:
            try: await rp.close()
            except: pass

        eng = views or likes
        rows.append({
            "hashtag": f"#{tag}",
            "platform": "Instagram",
            "title": title.replace('\n', ' '),
            "url": url,
            "views": views,
            "likes": likes,
            "engagement": eng or 0,
            "category": classify_category(title),
            "thumbnail": thumb,
            "scraped_at": datetime.now().isoformat(),
            "posted_on": datetime.now().isoformat(), # fallback for sorting
        })
    return rows

async def scrape_yt_tag(ctx, tag, limit=100):
    """Scrapes YT using exact logic from scrape_reels_to_excel.py"""
    rows = []
    page = await ctx.new_page()
    try:
        await page.goto(f"https://www.youtube.com/results?search_query=%23{tag}", wait_until="domcontentloaded", timeout=25000)
        await asyncio.sleep(3)
        for _ in range(8):
            await page.evaluate("window.scrollBy(0, 3000)")
            await asyncio.sleep(1)
            vids = await page.query_selector_all("ytd-video-renderer,ytd-rich-item-renderer")
            if len(vids) >= limit: break

        vids = await page.query_selector_all("ytd-video-renderer,ytd-rich-item-renderer")
        for v in vids[:limit]:
            t_el = await v.query_selector("#video-title,a#video-title")
            if not t_el: continue
            title = (await t_el.inner_text()).strip()
            if not title: continue
            
            views = None
            spans = await v.query_selector_all("#metadata-line span")
            for span in spans:
                st = (await span.inner_text()).strip()
                vm = re.search(r"([\d,\.]+(?:[\s\u00a0]+(?:crore|lakh))?[KMB]?)\s*views?", st, re.I)
                if vm:
                    views = parse_num(vm.group(1).strip())
                    if views: break
            if not views:
                aria = await t_el.get_attribute("aria-label") or ""
                vm2 = re.search(r"([\d,\.]+(?:[\s\u00a0]+(?:crore|lakh))?[KMB]?)\s*views?", aria, re.I)
                if vm2: views = parse_num(vm2.group(1).strip())
                
            href = await t_el.get_attribute("href") or ""
            url = fmt("https://www.youtube.com", href)
            vid_m = re.search(r"(?:v=|/shorts/)([A-Za-z0-9_-]{11})", href)
            vid_id = vid_m.group(1) if vid_m else ""
            thumb = f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg" if vid_id else ""

            rows.append({
                "hashtag": f"#{tag}",
                "platform": "YouTube",
                "title": title.replace('\n', ' '),
                "url": url,
                "views": views,
                "likes": None,
                "engagement": views or 0,
                "category": classify_category(title),
                "thumbnail": thumb,
                "scraped_at": datetime.now().isoformat(),
                "posted_on": datetime.now().isoformat(), # fallback for sorting
            })
        rows.sort(key=lambda x: x["views"] or 0, reverse=True)
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
            results=await asyncio.gather(*[_scrape_one(pw,t,platforms,per_tag) for t in batch], return_exceptions=True)
            for r in results:
                if isinstance(r,list): all_records.extend(r)
            done+=len(batch)
            if progress_cb: progress_cb(done/total,f"{done}/{total} hashtags")
    return all_records

async def _scrape_one(pw, tag, platforms, per_tag):
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
    
    # EXACT COOKIE INJECTION TO BYPASS LOGIN
    cks=[]
    if IG_SESSIONID: cks.append({"name":"sessionid","value":IG_SESSIONID,"domain":".instagram.com","path":"/","httpOnly":True,"secure":True,"sameSite":"Lax"})
    if IG_CSRFTOKEN: cks.append({"name":"csrftoken","value":IG_CSRFTOKEN,"domain":".instagram.com","path":"/","secure":True,"sameSite":"Lax"})
    if cks: await ctx.add_cookies(cks)
    
    try:
        if "Instagram" in platforms:
            ig_rows = await scrape_ig_tag(ctx, tag, per_tag)
            rows.extend(ig_rows)
        if "YouTube" in platforms:
            yt_rows = await scrape_yt_tag(ctx, tag, per_tag)
            rows.extend(yt_rows)
    finally:
        try: await ctx.close(); await browser.close()
        except: pass
    return rows

def run_sync(hashtags, platforms, per_tag, cb=None):
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

# ── APP STATE & DATA ──────────────────────────────────────────────────────────
BASE_TAGS = ["justdropped","newarrivals","productlaunch","newproduct","comingsoon",
    "trendingnow","whatshot","tiktokmademebuyit","instamademebuyit",
    "musthave","viralproduct","obsessed","shopnow","shopthelook",
    "giftideas","onlineshopping","founditonamazon","meeshofashion","meeshofinds",
    "unboxing","productreview","firstimpressions","triedandtested",
    "trendingproducts","trending","viral","indianfashion","amazonshopping","flipkartdeals"]
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

if "init" not in st.session_state:
    st.session_state.init=True
    st.session_state.sel_tags=BASE_TAGS[:5]
    st.session_state.sel_plats=["Instagram","YouTube"]
    st.session_state.per_tag=10
    st.session_state.sort_mode="Engagement ↓"

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
.tb{position:relative;background:#111;border-radius:8px 8px 0 0;overflow:hidden;}
.tb img{width:100%;height:145px;object-fit:cover;display:block;}
.cb{padding:7px 9px 9px;background:#fff;border-radius:0 0 8px 8px;box-shadow:0 2px 8px rgba(0,0,0,.09);}
.ct{font-size:11.5px;font-weight:600;color:#1e293b;line-height:1.3;margin:4px 0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
.cm{font-size:10.5px;color:#64748b;margin:2px 0;}
.pb{display:inline-block;padding:2px 6px;border-radius:4px;font-size:8.5px;font-weight:700;color:#fff;margin-right:4px;}
.ca{display:inline-block;padding:2px 7px;border-radius:11px;font-size:9.5px;background:#f0f4ff;color:#4361ee;margin-top:4px;}
</style>""", unsafe_allow_html=True)

st.markdown('<div class="hero"><div class="hero-t">📱 Social Trend Tracker</div>'
            '<div class="hero-s">Exact Script Extraction • Classified Categories</div></div>',
            unsafe_allow_html=True)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Settings")
    new_t=st.multiselect("Hashtags",BASE_TAGS,default=st.session_state.sel_tags)
    if new_t!=st.session_state.sel_tags: st.session_state.sel_tags=new_t
    custom=st.text_input("+ Custom tag",placeholder="kurtilovers")
    if custom:
        tag=custom.lower().strip("#").replace(" ","")
        if tag and tag not in st.session_state.sel_tags:
            if tag not in BASE_TAGS: BASE_TAGS.append(tag)
            st.session_state.sel_tags=st.session_state.sel_tags+[tag]
            st.rerun()
    new_p=st.multiselect("Platforms",["Instagram","YouTube"],default=st.session_state.sel_plats)
    if new_p!=st.session_state.sel_plats: st.session_state.sel_plats=new_p
    new_n=st.slider("Posts per hashtag per platform", 5, 100, st.session_state.per_tag)
    if new_n!=st.session_state.per_tag: st.session_state.per_tag=new_n
    st.divider()
    new_sort=st.radio("Sort / Rank by", ["Engagement ↓", "Most Recent ↓"], 
                      index=["Engagement ↓", "Most Recent ↓"].index(st.session_state.sort_mode))
    if new_sort!=st.session_state.sort_mode: st.session_state.sort_mode=new_sort
    st.divider()
    scrape_btn=st.button("🚀 Scrape Now",type="primary",use_container_width=True)
    st.divider()
    all_db=load_data()
    st.metric("Stored Records",len(all_db))
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
        st.success(f"✅ Scraped {len(new_recs)} posts.")
        st.rerun()
    except Exception as e:
        st.error(str(e))

all_data=load_data()
if not all_data:
    st.info("No data. Select hashtags → Scrape."); st.stop()

df=pd.DataFrame(all_data)
df["engagement"]=pd.to_numeric(df.get("engagement",0),errors="coerce").fillna(0)
df["views"]=pd.to_numeric(df.get("views",None),errors="coerce")
df["likes"]=pd.to_numeric(df.get("likes",None),errors="coerce")

df_sel=df[df["hashtag"].isin({f"#{t}" for t in sel_tags})].copy()
if df_sel.empty: df_sel=df.copy()

# ── VIEW FILTERS ──────────────────────────────────────────────────────────────
st.markdown("---")
cat_opts=["All"]+sorted(df_sel["category"].unique())
cf_val=st.selectbox("Filter by Category", cat_opts)

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

if st.session_state.sort_mode == "Engagement ↓":
    dff = dff.sort_values("engagement", ascending=False)
else:
    dff = dff.sort_values("scraped_at", ascending=False)

st.caption(f"Showing {len(dff)} posts.")
dff = dff.reset_index(drop=True)

for i in range(0,len(dff),4):
    cols=st.columns(4)
    for j,(_,r) in enumerate(dff.iloc[i:i+4].iterrows()):
        with cols[j]:
            plat = r.get("platform","")
            bc = "#e1306c" if plat=="Instagram" else "#ff0000"
            thumb = r.get("thumbnail","")
            if thumb:
                st.markdown(f'<div class="tb"><img src="{thumb}" onerror="this.parentNode.style.background=\'#f1f5f9\';this.style.display=\'none\'"></div>',unsafe_allow_html=True)
            else:
                em = "📸" if plat=="Instagram" else "▶"
                bg = "#fce7f3" if plat=="Instagram" else "#fee2e2"
                st.markdown(f'<div class="tb" style="background:{bg};display:flex;align-items:center;justify-content:center;font-size:28px">{em}</div>',unsafe_allow_html=True)
            
            metric = "  ·  ".join(filter(None,[f"👁 {fv(r.get('views'))}" if not pd.isna(r.get('views')) else None, f"❤️ {fv(r.get('likes'))}" if not pd.isna(r.get('likes')) else None])) or f"Eng: {fv(r.get('engagement'))}"
            
            st.markdown(f"""<div class="cb">
                <div><span class="pb" style="background:{bc}">{plat}</span> <span style="color:#4361ee;font-size:8.5px">{r.get("hashtag","")}</span></div>
                <div class="ct">{r.get("title","")}</div>
                <div class="cm">{metric}</div>
                <div class="ca">🏷 {r.get("category","")}</div>
            </div><br>""",unsafe_allow_html=True)
            st.link_button("Open ↗", r.get("url","#"), use_container_width=True)
