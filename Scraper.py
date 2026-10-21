"""
X Distribution — Multi-Industry Lead Scraper v3
===================================================
Scrapes Google Maps for leads across 4 industries in Malaysia & Singapore:
    1. Spa Businesses
    2. Soap Manufacturer Businesses
    3. Perfume Manufacturer Businesses
    4. Traditional Chinese Medicine (TCM) Businesses

Rules applied by the code:
    ✅ Skips companies already in your existing_leads.csv (name match that
       ignores suffixes such as Sdn Bhd / Pte Ltd)
    ✅ Skips large well-known brands (LARGE_BRAND_KEYWORDS)
    ✅ Checks whether each phone number is a MY/SG mobile (WhatsApp-capable).
       Office/landline numbers are KEPT, with a warning printed in the
       console; the CSV itself does not carry that flag.
    ✅ Stops searching a sector once it has 15 leads (min_leads). If the
       queries run out first, the end summary marks that sector with a warning.
       Default total = 4 sectors x 15 = 60 (CONFIG["total_target"] is not used).
    ✅ Must have a phone or an email when collected. Emails are looked up from
       websites AFTER collection, so in practice this means a phone number.
       Website / social link is optional.
    ✅ Output is ordered by the sector queue above

HOW TO USE EVERY TIME:
    1. Export your Google Sheet → File > Download > CSV
    2. Rename it to:  existing_leads.csv
    3. Place it in the same folder as this script
    4. Run:  python Scraper.py
    NOTE: never commit existing_leads.csv or the BGH_Leads_*.csv outputs
    (they contain business contact data) — see .gitignore.

Requirements:
    pip install selenium webdriver-manager requests beautifulsoup4 pandas
"""

import time
import random
import re
import os
import urllib.parse
from datetime import datetime

import requests
from bs4 import BeautifulSoup
import pandas as pd

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    print("Installing packages...")
    os.system("pip install selenium webdriver-manager requests beautifulsoup4 pandas")
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager


# ═══════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════

# All Malaysian states + major cities for broad coverage
MY_LOCATIONS = [
    # Klang Valley / Selangor
    "Kuala Lumpur", "Petaling Jaya", "Shah Alam", "Subang Jaya",
    "Klang", "Puchong", "Cheras", "Ampang", "Kepong", "Setapak",
    "Cyberjaya", "Putrajaya", "Kajang", "Semenyih", "Rawang",
    "Selayang", "Gombak", "Sepang", "Kuala Selangor", "Banting",
    # Penang
    "Penang", "Georgetown", "Butterworth", "Bukit Mertajam",
    "Bayan Lepas", "Nibong Tebal", "Sungai Petani Penang",
    # Johor
    "Johor Bahru", "Skudai", "Iskandar Puteri", "Batu Pahat",
    "Muar", "Kluang", "Kulai", "Pontian", "Segamat", "Kota Tinggi",
    # Perak
    "Ipoh", "Taiping", "Teluk Intan", "Sitiawan", "Kampar",
    "Batu Gajah", "Manjung", "Kuala Kangsar",
    # Negeri Sembilan
    "Seremban", "Port Dickson", "Nilai", "Bahau", "Rembau",
    # Melaka
    "Melaka", "Ayer Keroh", "Alor Gajah", "Jasin",
    # Pahang
    "Kuantan", "Temerloh", "Bentong", "Raub", "Mentakab",
    # Kedah
    "Alor Setar", "Sungai Petani", "Kulim", "Langkawi", "Baling",
    # Kelantan
    "Kota Bharu", "Pasir Mas", "Tanah Merah", "Gua Musang",
    # Terengganu
    "Kuala Terengganu", "Kemaman", "Dungun", "Besut",
    # Sabah
    "Kota Kinabalu", "Sandakan", "Tawau", "Lahad Datu", "Keningau",
    # Sarawak
    "Kuching", "Miri", "Sibu", "Bintulu", "Limbang",
    # Perlis
    "Kangar", "Arau",
    # Singapore
    "Singapore",
]

# Sector queue — ORDER HERE = ORDER IN OUTPUT
SECTORS = [
    {
        "name": "Spa",
        "min_leads": 15,
        "queries": (
            # City-specific searches across all states
            [f"spa wellness centre {loc}" for loc in MY_LOCATIONS] +
            [f"day spa {loc}" for loc in MY_LOCATIONS] +
            [f"beauty spa {loc}" for loc in MY_LOCATIONS] +
            [f"body spa {loc}" for loc in MY_LOCATIONS] +
            # General Malaysia-wide
            [
                "spa wellness Malaysia",
                "luxury spa Malaysia",
                "relaxation spa Malaysia",
                "halal spa Malaysia",
                "muslim friendly spa Malaysia",
                "ladies spa Malaysia",
                "wellness retreat Malaysia",
                "spa centre Malaysia",
            ]
        ),
    },
    {
        "name": "Soap Manufacturer",
        "min_leads": 15,
        "queries": (
            [f"soap manufacturer {loc}" for loc in MY_LOCATIONS] +
            [f"handmade soap {loc}" for loc in MY_LOCATIONS] +
            [f"natural soap {loc}" for loc in MY_LOCATIONS] +
            [
                "soap manufacturer Malaysia",
                "handmade soap manufacturer Malaysia",
                "organic soap manufacturer Malaysia",
                "natural soap manufacturer Malaysia",
                "halal soap manufacturer Malaysia",
                "cold process soap Malaysia",
                "artisan soap Malaysia",
                "soap OEM manufacturer Malaysia",
                "private label soap Malaysia",
                "herbal soap manufacturer Malaysia",
                "soap making company Malaysia",
                "homemade soap business Malaysia",
            ]
        ),
    },
    {
        "name": "Perfume Manufacturer",
        "min_leads": 15,
        "queries": (
            [f"perfume manufacturer {loc}" for loc in MY_LOCATIONS] +
            [f"fragrance company {loc}" for loc in MY_LOCATIONS] +
            [f"perfume shop {loc}" for loc in MY_LOCATIONS] +
            [
                "perfume manufacturer Malaysia",
                "fragrance manufacturer Malaysia",
                "local perfume brand Malaysia",
                "artisan perfume Malaysia",
                "attar perfume Malaysia",
                "OEM perfume manufacturer Malaysia",
                "private label perfume Malaysia",
                "natural fragrance manufacturer Malaysia",
                "halal perfume manufacturer Malaysia",
                "minyak wangi Malaysia",
                "perfume blending Malaysia",
                "bespoke perfume Malaysia",
            ]
        ),
    },
    {
        "name": "Traditional Chinese Medicine",
        "min_leads": 15,
        "queries": (
            [f"traditional chinese medicine {loc}" for loc in MY_LOCATIONS] +
            [f"TCM shop {loc}" for loc in MY_LOCATIONS] +
            [f"chinese herbal medicine {loc}" for loc in MY_LOCATIONS] +
            [f"sinseh {loc}" for loc in MY_LOCATIONS] +
            [
                "TCM clinic Malaysia",
                "chinese medicine hall Malaysia",
                "sinseh Malaysia",
                "TCM wellness centre Malaysia",
                "chinese herbal shop Malaysia",
                "kedai ubat cina Malaysia",
                "TCM acupuncture Malaysia",
                "chinese medicine practitioner Malaysia",
            ]
        ),
    },
]

CONFIG = {
    "total_target": 75,        # Minimum total leads across all sectors
    "results_per_query": 6,    # How many results to attempt per search
    "find_emails": True,       # Try to find emails from websites
    "delay": 2,                # Seconds between requests
    "output_file": f"BGH_Leads_v3_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
    "existing_leads_file": "existing_leads.csv",
}

# Large/well-known brands to skip
LARGE_BRAND_KEYWORDS = [
    "unilever", "l'oreal", "loreal", "procter", "gamble", "p&g",
    "johnson & johnson", "colgate", "henkel", "beiersdorf", "shiseido",
    "revlon", "maybelline", "garnier", "nivea", "dove", "lux", "palmolive",
    "bioderma", "cetaphil", "neutrogena", "avon", "oriflame", "amway",
    "chanel", "dior", "gucci", "ysl", "armani", "burberry", "versace",
    "watson", "guardian", "aeon", "parkson", "isetan",
]


# ═══════════════════════════════════════════════════════════
#  WHATSAPP NUMBER VALIDATOR
# ═══════════════════════════════════════════════════════════

# Valid MY/SG mobile prefixes reachable on WhatsApp
MOBILE_PATTERN = re.compile(
    r'(\+?6?0?1[0-9][\s\-]?\d{3,4}[\s\-]?\d{4})'   # +601x / 601x / 01x
    r'|(\+65[\s\-]?[89]\d{3}[\s\-]?\d{4})'           # Singapore +65 8x/9x
    r'|((?<!\d)[89]\d{3}[\s\-]?\d{4}(?!\d))',         # SG short form 8xxx/9xxx
    re.IGNORECASE
)

MY_MOBILE_PREFIXES = (
    "011", "012", "013", "014", "015", "016", "017", "018", "019",
    "+6011", "+6012", "+6013", "+6014", "+6015", "+6016", "+6017", "+6018", "+6019",
    "6011", "6012", "6013", "6014", "6015", "6016", "6017", "6018", "6019",
)


def is_whatsapp_number(phone: str) -> bool:
    """Return True if the phone number is a MY/SG mobile (WhatsApp-capable)."""
    if not phone or phone == "N/A":
        return False
    cleaned = phone.strip().replace(" ", "").replace("-", "")
    # Check Malaysian mobile prefixes
    for prefix in MY_MOBILE_PREFIXES:
        if cleaned.startswith(prefix):
            return True
    # Check Singapore mobile (+65 8x / +65 9x)
    if re.match(r'^\+65[89]\d{7}$', cleaned):
        return True
    if re.match(r'^65[89]\d{7}$', cleaned):
        return True
    return False


def extract_mobile_from_text(text: str) -> str:
    """Try to pull a mobile number out of a raw text string."""
    if not text or text == "N/A":
        return "N/A"
    matches = MOBILE_PATTERN.findall(text)
    for groups in matches:
        for match in groups:
            if match:
                candidate = match.strip()
                if is_whatsapp_number(candidate):
                    return candidate
    return "N/A"


# ═══════════════════════════════════════════════════════════
#  EXISTING LEADS LOADER
# ═══════════════════════════════════════════════════════════

def load_existing_leads(path: str) -> set:
    if not os.path.exists(path):
        print(f"  ℹ  '{path}' not found — no duplicates will be skipped.\n")
        return set()
    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
        name_col = next(
            (c for c in df.columns if "company" in c.lower() or "name" in c.lower()),
            df.columns[1] if len(df.columns) > 1 else df.columns[0]
        )
        existing = set(
            str(n).strip().lower() for n in df[name_col].dropna() if str(n).strip()
        )
        print(f"  ✅ Loaded {len(existing)} existing companies — these will be skipped.\n")
        return existing
    except Exception as e:
        print(f"  ⚠  Could not read '{path}': {e} — continuing without duplicate check.\n")
        return set()


def is_duplicate(name: str, existing: set) -> bool:
    norm = name.strip().lower()
    if norm in existing:
        return True
    suffix_re = re.compile(r'\b(sdn bhd|sdn|bhd|pte ltd|pte|ltd|llp|co\.|corp|berhad)\b')
    clean_new = suffix_re.sub("", norm).strip()
    for ex in existing:
        clean_ex = suffix_re.sub("", ex).strip()
        if clean_new and clean_ex and len(clean_new) > 4 and (
            clean_new == clean_ex
            or (len(clean_new) > 6 and clean_new in clean_ex)
            or (len(clean_ex) > 6 and clean_ex in clean_new)
        ):
            return True
    return False


# ═══════════════════════════════════════════════════════════
#  EMAIL FINDER
# ═══════════════════════════════════════════════════════════

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
JUNK_EMAIL_DOMAINS = {
    "sentry.io", "example.com", "wixpress.com", "squarespace.com",
    "wordpress.com", "google.com", "facebook.com", "wix.com",
    "godaddy.com", "shopify.com", "instagram.com", "tiktok.com",
}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def find_email(url: str, timeout: int = 8) -> str:
    if not url or url == "N/A":
        return "N/A"
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        emails = _parse_emails(r.text)
        if emails:
            return emails[0]
        base = url.rstrip("/")
        for path in ["/contact", "/contact-us", "/about", "/about-us", "/hubungi-kami"]:
            try:
                r2 = requests.get(base + path, headers=HEADERS, timeout=timeout)
                emails = _parse_emails(r2.text)
                if emails:
                    return emails[0]
                time.sleep(0.4)
            except Exception:
                continue
    except Exception:
        pass
    return "N/A"


def _parse_emails(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(" ")
    found = set(EMAIL_REGEX.findall(text))
    for a in soup.find_all("a", href=True):
        if a["href"].startswith("mailto:"):
            e = a["href"].replace("mailto:", "").split("?")[0].strip()
            if e:
                found.add(e)
    clean = [
        e.lower() for e in found
        if e.split("@")[-1].lower() not in JUNK_EMAIL_DOMAINS
        and not any(j in e.split("@")[-1].lower() for j in JUNK_EMAIL_DOMAINS)
    ]
    return sorted(clean, key=len)


# ═══════════════════════════════════════════════════════════
#  GOOGLE MAPS SCRAPER
# ═══════════════════════════════════════════════════════════

def create_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_argument(f"user-agent={HEADERS['User-Agent']}")
    opts.add_argument("--window-size=1280,900")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)


def scrape_maps(driver, query: str, industry: str, max_results: int = 6) -> list:
    url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"
    driver.get(url)
    results = []

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='feed'], div.Nv2PK"))
        )
        time.sleep(2)

        # Scroll results panel to load more
        try:
            panel = driver.find_element(By.CSS_SELECTOR, "div[role='feed']")
            for _ in range(4):
                driver.execute_script("arguments[0].scrollTop += 600;", panel)
                time.sleep(1)
        except Exception:
            pass

        cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK")[:max_results * 2]

        for card in cards:
            if len(results) >= max_results:
                break
            try:
                card.click()
                time.sleep(2.5)
                lead = _extract_details(driver, industry)
                if lead:
                    # Skip large brands
                    if any(kw in lead["company_name"].lower() for kw in LARGE_BRAND_KEYWORDS):
                        print(f"  ⊘ Large brand skipped: {lead['company_name']}")
                        continue
                    results.append(lead)
                    mobile_flag = "📱" if lead["has_mobile"] else "☎ "
                    print(f"  ✓ {lead['company_name']} | {mobile_flag} {lead['phone_whatsapp']}")
            except Exception:
                continue

    except Exception as e:
        print(f"  ✗ Error: {e}")

    return results


def _extract_details(driver, industry: str) -> dict:
    name = phone = website = "N/A"

    try:
        try:
            name = driver.find_element(
                By.CSS_SELECTOR, "h1.DUwDvf, h1[class*='fontHeadlineLarge']"
            ).text.strip()
        except Exception:
            pass

        try:
            el = driver.find_element(
                By.CSS_SELECTOR, "button[data-item-id^='phone'], [data-tooltip='Copy phone number']"
            )
            raw = el.get_attribute("aria-label") or el.text
            phone = raw.replace("Phone: ", "").strip()
        except Exception:
            pass

        try:
            el = driver.find_element(
                By.CSS_SELECTOR, "a[data-item-id='authority'], a[aria-label*='website' i]"
            )
            website = el.get_attribute("href") or "N/A"
            if "google.com/url" in website:
                params = urllib.parse.parse_qs(urllib.parse.urlparse(website).query)
                website = params.get("q", [website])[0]
        except Exception:
            pass

        if name == "N/A":
            return None

        # Check if phone is a mobile/WhatsApp number
        has_mobile = is_whatsapp_number(phone)

        return {
            "company_name": name,
            "industry": industry,
            "email": "N/A",
            "phone_whatsapp": phone,
            "website_social": website,
            "has_mobile": has_mobile,
        }
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════

def run():
    print("\n" + "═" * 62)
    print("  BGH Distribution — Multi-Industry Lead Scraper v3")
    print("  Industries: Spa | Soap Mfr | Perfume Mfr | TCM")
    print("═" * 62 + "\n")

    existing = load_existing_leads(CONFIG["existing_leads_file"])

    # leads_by_sector: { sector_name: [leads] }
    leads_by_sector = {s["name"]: [] for s in SECTORS}
    skipped_duplicate = 0
    skipped_no_contact = 0
    skipped_no_mobile = 0

    driver = None
    try:
        print("Starting Chrome browser...\n")
        driver = create_driver()

        for sector in SECTORS:
            sector_name = sector["name"]
            min_needed = sector["min_leads"]
            queries = sector["queries"][:]
            random.shuffle(queries)

            print(f"\n{'─'*62}")
            print(f"  SECTOR: {sector_name}  (target: {min_needed} leads)")
            print(f"{'─'*62}")

            for query in queries:
                collected = leads_by_sector[sector_name]
                if len(collected) >= min_needed:
                    break

                print(f"\n  🔍 {query}")
                raw = scrape_maps(
                    driver, query, sector_name,
                    max_results=CONFIG["results_per_query"]
                )

                seen_names = {l["company_name"].lower() for l in collected}

                for lead in raw:
                    name = lead["company_name"]

                    # Rule 1: skip duplicates from existing sheet
                    if is_duplicate(name, existing):
                        print(f"     ⊘ Already in sheet: {name}")
                        skipped_duplicate += 1
                        continue

                    # Rule 1b: skip duplicates within this run
                    if name.lower() in seen_names:
                        continue

                    # Rule 5: must have phone OR email (website/social is optional bonus)
                    has_contact = lead["phone_whatsapp"] != "N/A" or lead["email"] != "N/A"
                    if not has_contact:
                        print(f"     ⊘ No phone or email found, skipping: {name}")
                        skipped_no_contact += 1
                        continue

                    # Rule 2: phone must be mobile/WhatsApp capable
                    if lead["phone_whatsapp"] != "N/A" and not lead["has_mobile"]:
                        # Try to see if there's a mobile buried in the raw phone string
                        mobile = extract_mobile_from_text(lead["phone_whatsapp"])
                        if mobile != "N/A":
                            lead["phone_whatsapp"] = mobile
                            lead["has_mobile"] = True
                        else:
                            # Keep the number but flag it
                            print(f"     ⚠ Office number only (kept): {name} — {lead['phone_whatsapp']}")

                    collected.append(lead)
                    seen_names.add(name.lower())

                print(f"  → {sector_name}: {len(collected)}/{min_needed}")
                time.sleep(CONFIG["delay"])

            print(f"\n  ✅ {sector_name} done: {len(leads_by_sector[sector_name])} leads collected")

    except KeyboardInterrupt:
        print("\n\nStopped by user — saving what was collected so far...")
    finally:
        if driver:
            driver.quit()

    # ── Combine in sector order ──
    all_leads = []
    for sector in SECTORS:
        all_leads.extend(leads_by_sector[sector["name"]])

    if not all_leads:
        print("\nNo leads collected. Check your internet and try again.")
        return

    # ── Find emails ──
    if CONFIG["find_emails"]:
        print(f"\n{'═'*62}")
        print(f"  Scanning websites for emails ({len(all_leads)} companies)...")
        print("═" * 62)
        for i, lead in enumerate(all_leads):
            if lead["website_social"] != "N/A" and lead["email"] == "N/A":
                print(f"  [{i+1}/{len(all_leads)}] {lead['company_name']}...")
                lead["email"] = find_email(lead["website_social"])
                print(f"         → {lead['email']}")
                time.sleep(CONFIG["delay"])

    # ── Build & save CSV ──
    df = pd.DataFrame(all_leads)
    df = df[["company_name", "industry", "email", "phone_whatsapp", "website_social"]]
    df.columns = ["Company Name", "Industry", "Email", "Phone / WhatsApp", "Website / Social"]
    output_path = CONFIG["output_file"]
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    # ── Summary ──
    print(f"\n{'═'*62}")
    print(f"  ✅  DONE! {len(all_leads)} leads saved to: {output_path}")
    print(f"{'─'*62}")
    for sector in SECTORS:
        count = len(leads_by_sector[sector["name"]])
        status = "✅" if count >= sector["min_leads"] else "⚠ "
        print(f"  {status}  {sector['name']:<30} {count} leads")
    print(f"{'─'*62}")
    print(f"  ⊘  Skipped (already in sheet):  {skipped_duplicate}")
    print(f"  ⊘  Skipped (missing info):       {skipped_no_contact}")
    print(f"\n  HOW TO ADD TO GOOGLE SHEETS:")
    print(f"  1. Open {output_path} in Excel")
    print(f"  2. Select all → Ctrl+A → Ctrl+C")
    print(f"  3. Go to your Google Sheet → click next empty row")
    print(f"  4. Paste → Ctrl+Shift+V")
    print("═" * 62 + "\n")


if __name__ == "__main__":
    run()
