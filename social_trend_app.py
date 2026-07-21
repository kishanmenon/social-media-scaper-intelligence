"""
social_trend_app.py
Combined Hybrid App:
- Instagram: Direct GraphQL HTTP POST (No Playwright required)
- YouTube: Playwright Browser Scraper (from scrape_reels_to_excel.py)
- Category Rules: Exact keyword regex classification
"""
import streamlit as st
import asyncio, sys, os, re, json, threading, subprocess, time, io
from datetime import datetime, timedelta
from urllib.parse import quote
import requests
import pandas as pd

st.set_page_config(page_title="Trend Tracker", page_icon="📱", layout="wide")

# ── INSTALL CHROMIUM FOR YOUTUBE PLAYWRIGHT ────────────────────────────────────
@st.cache_resource
def install_chromium():
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"],
                       capture_output=True, text=True, timeout=120)
    except Exception: pass
install_chromium()

# ── CATEGORY CLASSIFIER (From Reference Code) ─────────────────────────────────
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

# ── UTILITIES ──────────────────────────────────────────────────────────────────
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
            except Exception: pass
    s2 = s.upper().replace(",","").replace("(","").replace(")","")
    m = re.search(r"([\d.]+)\s*([KMB]?)", s2)
    if not m: return None
    try:
        n = float(m.group(1))
        return int(n * {"K":1000,"M":1_000_000,"B":1_000_000_000}.get(m.group(2),1))
    except Exception: return None

def fmt(domain, link):
    if not link: return ""
    link = link.strip()
    if link.startswith("http"): return link
    return f"{domain}{link}" if link.startswith("/") else f"{domain}/{link}"

# ── DATA STORAGE ──────────────────────────────────────────────────────────────
DATA_FILE = "social_trends_data.json"

def load_data():
    if not os.path.exists(DATA_FILE): return []
    try: return json.load(open(DATA_FILE))
    except Exception: return []

def save_data(records):
    by_url = {}
    for r in records:
        url = r.get("url", "")
        if url: by_url[url] = r
    json.dump(list(by_url.values()), open(DATA_FILE, "w"), ensure_ascii=False, indent=2)

# ── INSTAGRAM GRAPHQL ENGINE (Direct HTTP POST) ───────────────────────────────
def extract_ig_shortcode(url_or_code: str) -> str:
    match = re.search(r"instagram\.com/(?:[^/]+/)?(?:reel|p)/([^/?#]+)", url_or_code)
    return match.group(1) if match else url_or_code.strip()

def fetch_ig_reel_graphql(shortcode_or_url: str):
    """Fetches Reel data via Instagram's direct GraphQL API"""
    shortcode = extract_ig_shortcode(shortcode_or_url)
    variables = json.dumps({"shortcode": shortcode})
    encoded_variables = quote(variables)

    payload = (
        f"av=0&__d=www&__user=0&__a=1&__req=u&__hs=20371.HYP%3Ainstagram_web_pkg.2.1...0"
        f"&dpr=1&__ccg=GOOD&__rev=1028249517&__s=ywybjm%3Aq4co81%3Adplvd8&__hsi=7559456450740095677"
        f"&__dyn=7xeUjG1mxu1syUbFp41twpUnwgU7SbzEdF8aUco2qwJw5ux609vCwjE1EE2Cw8G11wBz81s8hwGxu786a3a1YwBgao6C0Mo2swtUd8-U2zxe2GewGw9a361qw8Xxm16wa-0raazo7u3C2u2J0bS1LwTwKG0WE8oC1Iwqo5p0OwUQp1yU426V89F8uwm8jwhUaE4e1tyVrx60gm5oswFwtF85i5E"
        f"&__csr=geIAaiFliZllsBav4trBuTJ-KJ5WhnQyAnxeEWpBCC-hJADG9AgG4qpQ8zat5BypWy9eaRgBaJ2Xx2p6WgymmGDzQjJo8JJ4iKi8xObCjx50FzLF4-8DiwxDyGqoydV-ESQ9DLAB_GdDzFEsyUSeG8xmF9oymWyqyVFF84q5ooHohwuE5a0CU01kUUb81CE12E5V08m0WFA0ei80n2bLwjp42TOw2J-0rq04tUKp06PwEhy1u1ig4Dgy9wdW0D8n80rl0UxGtw53hEx2E1yPUy7U1J9Q0JFvc0cXwpyG4B6B2US01IAw2Bo0K215w0YEwj8"
        f"&__hsdp=gaQbh9gple4i4WuA2XCG7RVt5m8DxGU4K32awCF0GBcq1AyH40uWxe3AwboK5-0FE8UbkkU4-4o11XwQCyE9UswZweC4U6iq6UOewJyEhwBwjQ2259o1oE1E85u0km5Unw7Pwaau1CwMwkEeU1v82ew2rA0LoW0W8aO0Ewc6"
        f"&__hblp=0nE20wpGx6vxy2i1ryE9Gg6q1hwkE9WwkocUso4O2vDyof98K7o4-48hDwyLBx61HwkGg8VoGqawDxCGBwQxG6S0I8jwywXBCxKczEqxaax62m1FDxim1nw4axq0oC362m0iu7ohBxu11wEwfm0AE421xDwhEvwxzEvG2-3K0nO0zE1MUK0DA1DwgEizEW0Qp-2Awa8nxyi1fwRBwFwau68bE"
        f"&__comet_req=7&lsd=AdGtgRvhyjc&jazoest=21085&__spin_r=1028249517&__spin_b=trunk&__spin_t=1760073111"
        f"&__crn=comet.igweb.PolarisLoggedOutDesktopPostRouteNext&fb_api_caller_class=RelayModern"
        f"&fb_api_req_friendly_name=PolarisPostRootQuery&server_timestamps=true"
        f"&variables={encoded_variables}&doc_id=24368985919464652"
    )

    headers = {
        "accept": "*/*",
        "content-type": "application/x-www-form-urlencoded",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/141.0.0.0 Safari/537.36",
        "x-csrftoken": "YuvV-QRvpR2Ggzgk0cTg1T",
        "x-ig-app-id": "936619743392459",
        "Cookie": "csrftoken=YuvV-QRvpR2Ggzgk0cTg1T; mid=aOia4gALAAHSq3em2E34YEIFkMCC",
    }

    try:
        res = requests.post("https://www.instagram.com/graphql/query", headers=headers, data=payload, timeout=12)
        if res.status_code != 200: return None
        
        data = res.json()
        items = data.get("data", {}).get("xdt_api__v1__media__shortcode__web_info", {}).get("items", [])
        if not items: return None
        
        item = items[0]
        caption = item.get("caption", {}).get("text", "") or ""
        likes = item.get("like_count", 0)
        views = item.get("play_count") or item.get("view_count") or likes
        comments = item.get("comment_count", 0)
        
        taken_at = item.get("taken_at")
        posted_on = datetime.fromtimestamp(taken_at).strftime("%Y-%m-%d %H:%M") if taken_at else datetime.now().strftime("%Y-%m-%d %H:%M")

        candidates = item.get("image_versions2", {}).get("candidates", [])
        thumb = item.get("display_uri") or (candidates[0].get("url") if candidates else "")
        owner = item.get("owner", {}) or item.get("user", {})
        creator = f"@{owner.get('username', '')}" if owner.get('username') else ""

        return {
            "platform": "Instagram",
            "hashtag": "",
            "title": caption[:100].replace("\n", " ") if caption else f"Reel ({shortcode})",
            "description": caption.replace("\n", " "),
            "url": f"https://www.instagram.com/reel/{shortcode}/",
            "views": views,
            "likes": likes,
            "comments": comments,
            "engagement": views or likes or 0,
            "creator": creator,
            "thumbnail": thumb or "",
            "posted_on": posted_on,
            "category": classify_category(caption),
            "scraped_at": datetime.now().isoformat()
        }
    except Exception: return None

# ── YOUTUBE PLAYWRIGHT ENGINE (From Reference Script) ──────────────────────────
async def scrape_yt_tag_playwright(ctx, tag, limit=30):
    rows = []
    page = await ctx.new_page()
    try:
        await page.goto(f"https://www.youtube.com/results?search_query=%23{tag}", wait_until="domcontentloaded", timeout=25000)
        await asyncio.sleep(3)
        for _ in range(5):
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
                st_text = (await span.inner_text()).strip()
                vm = re.search(r"([\d,\.]+(?:[\s\u00a0]+(?:crore|lakh))?[KMB]?)\s*views?", st_text, re.I)
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
                "platform": "YouTube",
                "hashtag": f"#{tag}",
                "title": title.replace('\n', ' '),
                "description": "",
                "url": url,
                "views": views,
                "likes": None,
                "comments": None,
                "engagement": views or 0,
                "creator": "",
                "thumbnail": thumb,
                "posted_on": datetime.now().strftime("%Y-%m-%d"),
                "category": classify_category(title),
                "scraped_at": datetime.now().isoformat()
            })
    except Exception: pass
    finally:
        try: await page.close()
        except Exception: pass
    return rows

def run_yt_scrape_sync(tags, limit_per_tag):
    from playwright.async_api import async_playwright
    all_yt = []
    
    async def _runner():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-gpu"]
            )
            ctx = await browser.new_context(
                viewport={"width":1280,"height":800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
            )
            for tag in tags:
                recs = await scrape_yt_tag_playwright(ctx, tag, limit_per_tag)
                all_yt.extend(recs)
            await ctx.close()
            await browser.close()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_runner())
    finally:
        loop.close()
    return all_yt

# ── STREAMLIT UI ──────────────────────────────────────────────────────────────
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
.tb img{width:100%;height:180px;object-fit:cover;display:block;}
.cb{padding:10px;background:#fff;border-radius:0 0 8px 8px;box-shadow:0 2px 8px rgba(0,0,0,.09);}
.ct{font-size:12px;font-weight:600;color:#1e293b;line-height:1.3;margin:4px 0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
.cm{font-size:11px;color:#64748b;margin:3px 0;}
.pb-ig{display:inline-block;padding:2px 6px;border-radius:4px;font-size:9px;font-weight:700;color:#fff;background:#e1306c;}
.pb-yt{display:inline-block;padding:2px 6px;border-radius:4px;font-size:9px;font-weight:700;color:#fff;background:#ff0000;}
.ca{display:inline-block;padding:2px 8px;border-radius:11px;font-size:10px;background:#f0f4ff;color:#4361ee;margin-top:4px;}
</style>""", unsafe_allow_html=True)

st.markdown('<div class="hero"><div class="hero-t">📱 Social Trend Tracker</div>'
            '<div class="hero-s">Instagram GraphQL POST + YouTube Playwright Scraper</div></div>',
            unsafe_allow_html=True)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Fetch Controls")
    
    st.subheader("1. Instagram Reels")
    ig_input = st.text_area("Paste Instagram Reel URLs or Shortcodes (one per line)", 
                            value="https://www.instagram.com/oxford.mathematics/reel/DOvzTywjPGN/", height=80)
    
    st.divider()
    st.subheader("2. YouTube Hashtags")
    yt_tags_input = st.text_input("YouTube Hashtags (comma-separated)", value="kurti, trendingproducts")
    yt_limit = st.slider("Videos per YouTube hashtag", 5, 50, 15)
    
    st.divider()
    fetch_btn = st.button("🚀 Scrape & Process", type="primary", use_container_width=True)
    
    all_db = load_data()
    st.metric("Stored Items", len(all_db))
    if st.button("🗑 Clear Stored Data", use_container_width=True):
        save_data([])
        st.rerun()

# ── EXECUTION ─────────────────────────────────────────────────────────────────
if fetch_btn:
    new_records = []
    
    # Process Instagram
    if ig_input.strip():
        lines = [l.strip() for l in ig_input.splitlines() if l.strip()]
        st.info(f"📸 Querying {len(lines)} Instagram reels via GraphQL...")
        for line in lines:
            rec = fetch_ig_reel_graphql(line)
            if rec: new_records.append(rec)
            
    # Process YouTube
    if yt_tags_input.strip():
        tags = [t.strip().lstrip("#") for t in yt_tags_input.split(",") if t.strip()]
        st.info(f"▶️ Executing Playwright for YouTube: #{', #'.join(tags)}...")
        yt_records = run_yt_scrape_sync(tags, yt_limit)
        new_records.extend(yt_records)
        
    if new_records:
        save_data(load_data() + new_records)
        st.success(f"✅ Successfully processed {len(new_records)} total records!")
        st.rerun()
    else:
        st.error("❌ No data captured. Check your shortcodes/URLs or hashtags.")

# ── DASHBOARD DISPLAY ─────────────────────────────────────────────────────────
all_data = load_data()
if not all_data:
    st.info("No data stored yet. Enter shortcodes or hashtags in the sidebar and click 'Scrape & Process'.")
    st.stop()

df = pd.DataFrame(all_data)

c1, c2, c3 = st.columns(3)
with c1:
    plat_filter = st.selectbox("Platform Filter", ["All", "Instagram", "YouTube"])
with c2:
    categories = ["All"] + sorted(list(df["category"].unique()))
    sel_cat = st.selectbox("Category Filter", categories)
with c3:
    sort_by = st.selectbox("Sort by", ["Engagement ↓", "Views ↓"])

dff = df.copy()
if plat_filter != "All": dff = dff[dff["platform"] == plat_filter]
if sel_cat != "All": dff = dff[dff["category"] == sel_cat]

if sort_by == "Engagement ↓": dff = dff.sort_values("engagement", ascending=False)
else: dff = dff.sort_values("views", ascending=False)

dff = dff.reset_index(drop=True)

csv_b = io.StringIO()
dff.to_csv(csv_b, index=False)
st.download_button("⬇️ Export Data CSV", csv_b.getvalue(), "trends.csv", "text/csv")

def format_num(val):
    if val is None or pd.isna(val) or val == 0: return "—"
    v = int(val)
    if v >= 1_000_000: return f"{v/1_000_000:.1f}M"
    if v >= 1_000: return f"{v/1_000:.0f}K"
    return str(v)

st.caption(f"Displaying **{len(dff)}** posts.")

for i in range(0, len(dff), 4):
    cols = st.columns(4)
    for j, (_, r) in enumerate(dff.iloc[i:i+4].iterrows()):
        with cols[j]:
            plat = r.get("platform", "")
            badge_class = "pb-ig" if plat == "Instagram" else "pb-yt"
            thumb = r.get("thumbnail")
            
            if thumb:
                st.markdown(f'<div class="tb"><img src="{thumb}" onerror="this.parentNode.style.background=\'#f1f5f9\';this.style.display=\'none\'"></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="tb" style="background:#fce7f3;display:flex;align-items:center;justify-content:center;height:180px;font-size:28px">🎬</div>', unsafe_allow_html=True)
            
            creator_text = f"👤 {r.get('creator')}" if r.get('creator') else ""
            posted_text = f"🕐 {r.get('posted_on')}" if r.get('posted_on') else ""
            tag_text = f" {r.get('hashtag')}" if r.get('hashtag') else ""
            
            st.markdown(f"""<div class="cb">
                <div><span class="{badge_class}">{plat}</span> <span style="font-size:10px;color:#64748b;">{tag_text}</span></div>
                <div class="ct">{r.get("title","")}</div>
                <div class="cm">{creator_text}</div>
                <div class="cm">{posted_text}</div>
                <div class="cm">👁 {format_num(r.get('views'))}  ·  ❤️ {format_num(r.get('likes'))}</div>
                <div class="ca">🏷 {r.get("category","")}</div>
            </div><br>""", unsafe_allow_html=True)
            st.link_button(f"Open {plat} ↗", r.get("url", "#"), use_container_width=True)
