"""
social_trend_app.py
Unified Hashtag Scraper & Trend Tracker:
- Instagram: Playwright grid discovery + GraphQL POST metadata extraction (doc_id=24368985919464652).
- YouTube: Playwright hashtag search & element metadata extraction.
- Classification: Keyword regex categorization.
- UI: Streamlit grid display, time window tabs (L30/L7/24h/Lifetime), export CSV, and sort options.
"""
import streamlit as st
import asyncio, sys, os, re, json, threading, subprocess, time, io
from datetime import datetime, timedelta
from urllib.parse import quote
import requests
import pandas as pd

st.set_page_config(page_title="Trend Tracker", page_icon="📱", layout="wide")

# ── INSTALL CHROMIUM ──────────────────────────────────────────────────────────
@st.cache_resource
def install_chromium():
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"],
                       capture_output=True, text=True, timeout=120)
    except Exception: pass
install_chromium()

def secret(k, d=""):
    try: return st.secrets.get(k, d) or d
    except Exception: return os.environ.get(k, d)

IG_SESSIONID = secret("IG_SESSIONID")
IG_CSRFTOKEN = secret("IG_CSRFTOKEN")

# ── CATEGORY CLASSIFIER ───────────────────────────────────────────────────────
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

# ── INSTAGRAM GRAPHQL METADATA QUERY ─────────────────────────────────────────
def fetch_ig_metadata_graphql(shortcode: str, tag: str):
    """Executes direct GraphQL POST query to obtain exact reel metadata"""
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

    csrf = IG_CSRFTOKEN or "YuvV-QRvpR2Ggzgk0cTg1T"
    cookie_str = f"csrftoken={csrf}; mid=aOia4gALAAHSq3em2E34YEIFkMCC"
    if IG_SESSIONID: cookie_str += f"; sessionid={IG_SESSIONID}"

    headers = {
        "accept": "*/*",
        "content-type": "application/x-www-form-urlencoded",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
        "x-csrftoken": csrf,
        "x-ig-app-id": "936619743392459",
        "Cookie": cookie_str,
    }

    try:
        res = requests.post("https://www.instagram.com/graphql/query", headers=headers, data=payload, timeout=12)
        if res.status_code != 200: return None
        data = res.json()
        items = data.get("data", {}).get("xdt_api__v1__media__shortcode__web_info", {}).get("items", [])
        if not items: return None

        item = items[0]
        caption = item.get("caption", {}).get("text", "") or ""
        likes = item.get("like_count")
        views = item.get("play_count") or item.get("view_count") or likes
        comments = item.get("comment_count")
        
        taken_at = item.get("taken_at")
        posted_on = datetime.fromtimestamp(taken_at).isoformat() if taken_at else datetime.now().isoformat()

        candidates = item.get("image_versions2", {}).get("candidates", [])
        thumb = item.get("display_uri") or (candidates[0].get("url") if candidates else "")
        owner = item.get("owner", {}) or item.get("user", {})
        creator = f"@{owner.get('username', '')}" if owner.get('username') else ""

        title = caption[:100].replace('\n', ' ') if caption else f"#{tag} reel"
        desc = caption.replace('\n', ' ')
        cat = classify_category(f"{title} {desc} {tag}")

        return {
            "platform": "Instagram",
            "content_type": "Reel",
            "hashtag": f"#{tag}",
            "url": f"https://www.instagram.com/reel/{shortcode}/",
            "title": title,
            "description": desc,
            "creator": creator,
            "thumbnail": thumb or "",
            "posted_on": posted_on,
            "views": views,
            "likes": likes,
            "comments": comments,
            "engagement": views or likes or 0,
            "category": cat,
            "scraped_at": datetime.now().isoformat()
        }
    except Exception: return None

# ── INSTAGRAM PLAYWRIGHT GRID DISCOVERY ────────────────────────────────────────
async def scrape_ig(ctx, tag, limit=15):
    page = await ctx.new_page()
    items_scraped = []
    found_urls = []
    
    try:
        await page.goto(f"https://www.instagram.com/explore/tags/{tag}/", wait_until="domcontentloaded", timeout=25000)
        await asyncio.sleep(4)
        
        if "login" not in page.url and "accounts" not in page.url:
            # Click Recent tab if present
            for recent_sel in ["span:text-is('Recent')", "div[role='tab']:has-text('Recent')", "a[href*='recent']"]:
                try:
                    tab = page.locator(recent_sel).first
                    if await tab.count():
                        await tab.click()
                        await asyncio.sleep(2)
                        break
                except Exception: continue

            # Scroll grid to reveal reels
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, 1500)")
                await asyncio.sleep(0.8)

            links = await page.locator("a[href*='/reel/'], a[href*='/p/']").all()
            seen_codes = set()
            for el in links:
                href = await el.get_attribute("href")
                if not href: continue
                m = re.search(r"/(?:reel|p)/([^/?#]+)", href)
                if m:
                    code = m.group(1)
                    if code not in seen_codes:
                        seen_codes.add(code)
                        
                        img_el = el.locator("img").first
                        alt = (await img_el.get_attribute("alt") if await img_el.count() else "") or ""
                        src = (await img_el.get_attribute("src") if await img_el.count() else "") or ""
                        
                        found_urls.append((code, alt, src))
                        if len(found_urls) >= limit: break
    except Exception: pass
    finally:
        try: await page.close()
        except Exception: pass

    # Fetch exact metadata via GraphQL for each discovered shortcode
    for code, alt, src in found_urls[:limit]:
        rec = fetch_ig_metadata_graphql(code, tag)
        if rec:
            items_scraped.append(rec)
        else:
            # Fallback if GraphQL query is rate limited
            title = alt[:100] if alt else f"#{tag} reel"
            items_scraped.append({
                "platform": "Instagram", "content_type": "Reel",
                "hashtag": f"#{tag}", "url": f"https://www.instagram.com/reel/{code}/",
                "title": title.replace('\n', ' '), "description": alt.replace('\n', ' '),
                "creator": "", "thumbnail": src, "posted_on": datetime.now().isoformat(),
                "views": None, "likes": None, "engagement": 0,
                "category": classify_category(f"{title} {alt} {tag}"),
                "scraped_at": datetime.now().isoformat()
            })

    return items_scraped

# ── YOUTUBE PLAYWRIGHT SCRAPER ────────────────────────────────────────────────
async def scrape_yt(ctx, tag, limit=25):
    rows = []
    page = await ctx.new_page()
    try:
        await page.goto(f"https://www.youtube.com/results?search_query=%23{tag}", wait_until="domcontentloaded", timeout=25000)
        await asyncio.sleep(3)
        for _ in range(6):
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
                
            posted_on = datetime.now().isoformat()
            for span in spans:
                st_text = (await span.inner_text()).strip()
                m2 = re.search(r"(\d+)\s*(second|minute|hour|day|week|month|year)s?\s*ago", st_text, re.I)
                if m2:
                    n2 = int(m2.group(1))
                    unit = m2.group(2).lower()
                    delta_map = {"second": 1, "minute": 60, "hour": 3600, "day": 86400, "week": 604800, "month": 2592000, "year": 31536000}
                    secs = n2 * delta_map.get(unit, 86400)
                    posted_on = (datetime.now() - timedelta(seconds=secs)).isoformat()
                    break

            ch = await v.query_selector("#channel-name a,ytd-channel-name a")
            channel = (await ch.inner_text()).strip() if ch else ""
            href = await t_el.get_attribute("href") or ""
            is_s = "/shorts/" in href
            
            vid_m = re.search(r"(?:v=|/shorts/)([A-Za-z0-9_-]{11})", href)
            vid_id = vid_m.group(1) if vid_m else ""
            thumb = f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg" if vid_id else ""

            rows.append({
                "platform": "YouTube",
                "content_type": "Shorts" if is_s else "Video",
                "hashtag": f"#{tag}",
                "title": title.replace('\n', ' '),
                "description": "",
                "url": fmt("https://www.youtube.com", href),
                "views": views,
                "likes": None,
                "comments": None,
                "engagement": views or 0,
                "creator": channel,
                "thumbnail": thumb,
                "posted_on": posted_on,
                "category": classify_category(f"{title} {tag}"),
                "scraped_at": datetime.now().isoformat()
            })
    except Exception: pass
    finally:
        try: await page.close()
        except Exception: pass
    return rows

# ── SCRAPE RUNNER ─────────────────────────────────────────────────────────────
async def _run_all(hashtags, platforms, per_tag, progress_cb):
    from playwright.async_api import async_playwright
    all_records = []
    BATCH = 3
    async with async_playwright() as pw:
        total = len(hashtags); done = 0
        for i in range(0, total, BATCH):
            batch = hashtags[i:i+BATCH]
            results = await asyncio.gather(*[_scrape_one(pw, t, platforms, per_tag) for t in batch], return_exceptions=True)
            for r in results:
                if isinstance(r, list): all_records.extend(r)
            done += len(batch)
            if progress_cb: progress_cb(done/total, f"{done}/{total} hashtags")
    return all_records

async def _scrape_one(pw, tag, platforms, per_tag):
    rows = []
    args = ["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-gpu",
            "--ignore-certificate-errors", "--disable-dev-shm-usage", "--disable-setuid-sandbox", "--no-zygote", "--mute-audio"]
    try: browser = await pw.chromium.launch(headless=True, args=args)
    except Exception:
        args.append("--single-process")
        browser = await pw.chromium.launch(headless=True, args=args)
        
    ctx = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        extra_http_headers={"Accept-Language": "en-IN,en;q=0.9"})
    await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
    
    cks = []
    if IG_SESSIONID: cks.append({"name": "sessionid", "value": IG_SESSIONID, "domain": ".instagram.com", "path": "/", "httpOnly": True, "secure": True, "sameSite": "Lax"})
    if IG_CSRFTOKEN: cks.append({"name": "csrftoken", "value": IG_CSRFTOKEN, "domain": ".instagram.com", "path": "/", "secure": True, "sameSite": "Lax"})
    if cks: await ctx.add_cookies(cks)
    
    try:
        if "Instagram" in platforms:
            try: rows.extend(await scrape_ig(ctx, tag, per_tag))
            except Exception: pass
        if "YouTube" in platforms:
            try: rows.extend(await scrape_yt(ctx, tag, per_tag))
            except Exception: pass
    finally:
        try: await ctx.close(); await browser.close()
        except Exception: pass
    return rows

def run_sync(hashtags, platforms, per_tag, cb=None):
    result = {}; exc = []; ps = {"f": 0, "m": "Starting..."}
    def _p(f, m): ps["f"] = f; ps["m"] = m
    def _t():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try: result["r"] = loop.run_until_complete(_run_all(hashtags, platforms, per_tag, _p))
        except Exception as e: exc.append(e)
        finally: loop.close()
    t = threading.Thread(target=_t, daemon=True); t.start()
    while t.is_alive():
        if cb:
            try: cb(ps["f"], ps["m"])
            except Exception: pass
        time.sleep(1)
    t.join(timeout=10)
    if exc: raise exc[0]
    return result.get("r", [])

# ── SESSION STATE ─────────────────────────────────────────────────────────────
BASE_TAGS = ["justdropped", "newarrivals", "productlaunch", "newproduct", "comingsoon",
             "trendingnow", "whatshot", "tiktokmademebuyit", "instamademebuyit",
             "musthave", "viralproduct", "obsessed", "shopnow", "shopthelook",
             "kurtidesign", "meeshofinds", "trendingproducts"]

if "sel_tags" not in st.session_state: st.session_state.sel_tags = BASE_TAGS[:5]
if "sel_plats" not in st.session_state: st.session_state.sel_plats = ["Instagram", "YouTube"]
if "per_tag" not in st.session_state: st.session_state.per_tag = 10
if "sort_mode" not in st.session_state: st.session_state.sort_mode = "Engagement ↓"

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
.tb img{width:100%;height:150px;object-fit:cover;display:block;}
.cb{padding:8px 10px 10px;background:#fff;border-radius:0 0 8px 8px;box-shadow:0 2px 8px rgba(0,0,0,.09);}
.ct{font-size:11.5px;font-weight:600;color:#1e293b;line-height:1.3;margin:4px 0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
.cm{font-size:10.5px;color:#64748b;margin:2px 0;}
.pb-ig{display:inline-block;padding:2px 6px;border-radius:4px;font-size:8.5px;font-weight:700;color:#fff;background:#e1306c;}
.pb-yt{display:inline-block;padding:2px 6px;border-radius:4px;font-size:8.5px;font-weight:700;color:#fff;background:#ff0000;}
.ca{display:inline-block;padding:2px 8px;border-radius:11px;font-size:9.5px;background:#f0f4ff;color:#4361ee;margin-top:4px;}
</style>""", unsafe_allow_html=True)

st.markdown('<div class="hero"><div class="hero-t">📱 Social Trend Tracker</div>'
            '<div class="hero-s">Playwright Hashtag Discovery + Direct GraphQL Metadata Extraction</div></div>',
            unsafe_allow_html=True)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Settings")
    new_t = st.multiselect("Hashtags", BASE_TAGS, default=st.session_state.sel_tags)
    if new_t != st.session_state.sel_tags: st.session_state.sel_tags = new_t
    
    custom = st.text_input("+ Custom tag", placeholder="kurtilovers")
    if custom:
        tag = custom.lower().strip("#").replace(" ", "")
        if tag and tag not in st.session_state.sel_tags:
            if tag not in BASE_TAGS: BASE_TAGS.append(tag)
            st.session_state.sel_tags = st.session_state.sel_tags + [tag]
            st.rerun()
            
    new_p = st.multiselect("Platforms", ["Instagram", "YouTube"], default=st.session_state.sel_plats)
    if new_p != st.session_state.sel_plats: st.session_state.sel_plats = new_p
    
    new_n = st.slider("Posts per hashtag per platform", 5, 50, st.session_state.per_tag)
    if new_n != st.session_state.per_tag: st.session_state.per_tag = new_n
    
    st.divider()
    new_sort = st.radio("Sort / Rank by", ["Engagement ↓", "Most Recent ↓"], 
                        index=["Engagement ↓", "Most Recent ↓"].index(st.session_state.sort_mode))
    if new_sort != st.session_state.sort_mode: st.session_state.sort_mode = new_sort
    
    st.divider()
    scrape_btn = st.button("🚀 Scrape Now", type="primary", use_container_width=True)
    
    st.divider()
    all_db = load_data()
    st.metric("Stored Records", len(all_db))
    if st.button("🗑 Clear Stored Data", use_container_width=True):
        save_data([])
        st.rerun()

sel_tags = st.session_state.sel_tags
sel_plats = st.session_state.sel_plats
per_n = st.session_state.per_tag

# ── EXECUTE SCRAPE ────────────────────────────────────────────────────────────
if scrape_btn and sel_tags:
    prog = st.progress(0, "Starting...")
    status = st.empty()
    def cb(f, m):
        try: prog.progress(min(f, 0.99), m); status.info(m)
        except Exception: pass
    try:
        new_recs = run_sync(sel_tags, sel_plats, per_n, cb)
        save_data(load_data() + new_recs)
        prog.empty(); status.empty()
        st.success(f"✅ Scraped {len(new_recs)} posts.")
        st.rerun()
    except Exception as e:
        st.error(str(e))

# ── FILTER & SORT DATA ────────────────────────────────────────────────────────
all_data = load_data()
if not all_data:
    st.info("No data stored. Select hashtags and click 'Scrape Now'.")
    st.stop()

df = pd.DataFrame(all_data)
df["engagement"] = pd.to_numeric(df.get("engagement", 0), errors="coerce").fillna(0)
df["views"] = pd.to_numeric(df.get("views", None), errors="coerce")
df["likes"] = pd.to_numeric(df.get("likes", None), errors="coerce")
df["uploaded_at"] = pd.to_datetime(df.get("posted_on", ""), errors="coerce")

df_sel = df[df["hashtag"].isin({f"#{t}" for t in sel_tags})].copy()
if df_sel.empty: df_sel = df.copy()

st.markdown("---")
cat_opts = ["All"] + sorted([str(c) for c in df_sel["category"].unique()])
cf_val = st.selectbox("Filter by Category", cat_opts)

dff = df_sel.copy()
if sel_plats: dff = dff[dff["platform"].isin(sel_plats)]
if cf_val != "All": dff = dff[dff["category"] == cf_val]

csv_b = io.StringIO(); dff.to_csv(csv_b, index=False)
st.download_button("⬇️ Export CSV", csv_b.getvalue(), "trends.csv", "text/csv")

if dff.empty: st.info("No data matches selected filters."); st.stop()

def apply_sort(data_df):
    if st.session_state.sort_mode == "Engagement ↓":
        return data_df.sort_values("engagement", ascending=False)
    else:
        return data_df.sort_values("uploaded_at", ascending=False, na_position="last")

def fv(v):
    if v is None or pd.isna(v): return "—"
    v = int(v)
    if v >= 1_000_000: return f"{v/1_000_000:.1f}M"
    if v >= 1_000: return f"{v/1_000:.0f}K"
    return str(v)

def render_grid(data, label, max_n=60):
    if data.empty: st.info("No posts for this view."); return
    d = apply_sort(data).head(max_n).reset_index(drop=True)
    st.caption(f"Showing **{len(d)}** posts.")
    
    for i in range(0, len(d), 4):
        cols = st.columns(4)
        for j, (_, r) in enumerate(d.iloc[i:i+4].iterrows()):
            with cols[j]:
                plat = r.get("platform", "")
                badge_class = "pb-ig" if plat == "Instagram" else "pb-yt"
                thumb = r.get("thumbnail", "")
                
                if thumb:
                    st.markdown(f'<div class="tb"><img src="{thumb}" onerror="this.parentNode.style.background=\'#f1f5f9\';this.style.display=\'none\'"></div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="tb" style="background:#fce7f3;display:flex;align-items:center;justify-content:center;height:150px;font-size:28px">🎬</div>', unsafe_allow_html=True)
                
                creator = f"👤 {r.get('creator')}" if r.get('creator') else ""
                posted = str(r.get('posted_on', ''))[:10]
                posted_str = f"🕐 {posted}" if posted else ""
                
                metric = "  ·  ".join(filter(None, [
                    f"👁 {fv(r.get('views'))}" if not pd.isna(r.get('views')) else None,
                    f"❤️ {fv(r.get('likes'))}" if not pd.isna(r.get('likes')) else None
                ])) or f"Eng: {fv(r.get('engagement'))}"
                
                st.markdown(f"""<div class="cb">
                    <div><span class="{badge_class}">{plat}</span> <span style="color:#4361ee;font-size:9px">{r.get("hashtag","")}</span></div>
                    <div class="ct">{r.get("title","")}</div>
                    {"<div class='cm'>"+creator+"</div>" if creator else ""}
                    {"<div class='cm'>"+posted_str+"</div>" if posted_str else ""}
                    <div class="cm">{metric}</div>
                    <div class="ca">🏷 {r.get("category","")}</div>
                </div><br>""", unsafe_allow_html=True)
                st.link_button(f"Open {plat} ↗", r.get("url", "#"), use_container_width=True)

# ── TIME WINDOW TABS ──────────────────────────────────────────────────────────
now = datetime.now()
ua = pd.to_datetime(dff["uploaded_at"], errors="coerce")
d30 = dff[ua.notna() & (ua >= now - timedelta(days=30))]
d7  = dff[ua.notna() & (ua >= now - timedelta(days=7))]
d1  = dff[ua.notna() & (ua >= now - timedelta(days=1))]

t_l30, t_l7, t_l1, t_all, t_stats = st.tabs([
    f"📅 L30 Days ({len(d30)})",
    f"📅 L7 Days ({len(d7)})",
    f"📅 Last 24h ({len(d1)})",
    f"🏆 Lifetime ({len(dff)})",
    "📊 Stats"
])

with t_l30: render_grid(d30, "l30")
with t_l7: render_grid(d7, "l7")
with t_l1: render_grid(d1, "l1d")
with t_all: render_grid(dff, "life")

with t_stats:
    st.subheader("📊 Performance Summary")
    s1, s2, s3, s4 = st.columns(4)
    with s1: st.metric("Total Items", len(dff))
    with s2: st.metric("Instagram", len(dff[dff["platform"] == "Instagram"]))
    with s3: st.metric("YouTube", len(dff[dff["platform"] == "YouTube"]))
    with s4: st.metric("Categories", dff["category"].nunique())
    st.divider()
    st.markdown("#### Top Categories by Items")
    st.bar_chart(dff["category"].value_counts())
