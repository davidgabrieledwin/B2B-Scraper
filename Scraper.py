"""
BGH Distribution — B2B Lead Scraper
====================================
Searches Google Maps for potential customers (spas, pharmacies, hotels, etc.)
across Malaysia and Singapore, then attempts to find contact emails from
each business's website.

Outputs a CSV ready to paste into Google Sheets.

Requirements:
    pip install selenium webdriver-manager requests beautifulsoup4 pandas

Usage:
    python bgh_lead_scraper.py

Edit the CONFIG section below to customise your search.
"""

import time
import random
import re
import csv
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
    print("Installing required packages...")
    os.system("pip install selenium webdriver-manager requests beautifulsoup4 pandas")
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager

# ─────────────────────────────────────────────
#  CONFIG — Edit this section to customise
# ─────────────────────────────────────────────

CONFIG = {
    # Business types to search for
    "business_types": [
        "spa",
        "pharmacy",
        "hotel",
        "yoga studio",
        "beauty salon",
        "health store",
        "massage centre",
        "aromatherapy shop",
        "organic shop",
        "gym",
    ],

    # Cities to search in
    "cities": [
        "Kuala Lumpur, Malaysia",
        "Petaling Jaya, Malaysia",
        "Penang, Malaysia",
        "Johor Bahru, Malaysia",
        "Shah Alam, Malaysia",
        "Singapore",
    ],

    # How many leads to collect in total
    "target_leads": 15,

    # How many results to grab per search query
    "results_per_query": 5,

    # Output CSV filename
    "output_file": f"BGH_Leads_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",

    # Try to find email from website? (slower but more complete)
    "find_emails": True,

    # Seconds to wait between requests (be polite to servers)
    "delay_between_requests": 2,
}

# ─────────────────────────────────────────────
#  EMAIL FINDER
# ─────────────────────────────────────────────

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
SKIP_EMAIL_DOMAINS = {"sentry.io", "example.com", "wixpress.com", "squarespace.com",
                      "wordpress.com", "google.com", "facebook.com", "png", "jpg", "gif"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def find_email_from_website(url: str, timeout: int = 8) -> str:
    """Attempt to extract a contact email from a website."""
    if not url or url == "N/A":
        return "N/A"

    try:
        # First try the homepage
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        emails = _extract_emails(resp.text, url)
        if emails:
            return emails[0]

        # Try common contact pages
        base = url.rstrip("/")
        for path in ["/contact", "/contact-us", "/about", "/about-us"]:
            try:
                r = requests.get(base + path, headers=HEADERS, timeout=timeout)
                emails = _extract_emails(r.text, url)
                if emails:
                    return emails[0]
                time.sleep(0.5)
            except Exception:
                continue

    except Exception:
        pass

    return "N/A"


def _extract_emails(html: str, source_url: str) -> list:
    """Extract and filter emails from HTML content."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove scripts and styles
    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    found = set(EMAIL_REGEX.findall(text))

    # Also check mailto links
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:"):
            email = href.replace("mailto:", "").split("?")[0].strip()
            if email:
                found.add(email)

    # Filter junk
    clean = []
    for e in found:
        domain = e.split("@")[-1].lower()
        if domain not in SKIP_EMAIL_DOMAINS and not any(
            skip in domain for skip in SKIP_EMAIL_DOMAINS
        ):
            clean.append(e.lower())

    # Prefer shorter, cleaner emails
    clean.sort(key=lambda x: len(x))
    return clean


# ─────────────────────────────────────────────
#  GOOGLE MAPS SCRAPER
# ─────────────────────────────────────────────

def create_driver(headless: bool = False) -> webdriver.Chrome:
    """Create and return a Chrome WebDriver."""
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument(f"user-agent={HEADERS['User-Agent']}")
    options.add_argument("--window-size=1280,900")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def scrape_maps(driver, query: str, max_results: int = 5) -> list:
    """
    Search Google Maps for a query and extract business listings.
    Returns a list of dicts with keys: name, industry, address, phone, website.
    """
    encoded = urllib.parse.quote(query)
    url = f"https://www.google.com/maps/search/{encoded}"
    driver.get(url)

    results = []

    try:
        # Wait for results panel
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div[role='feed'], div.Nv2PK")
            )
        )
        time.sleep(2)

        # Scroll results panel to load more
        try:
            panel = driver.find_element(
                By.CSS_SELECTOR, "div[role='feed']"
            )
            for _ in range(3):
                driver.execute_script(
                    "arguments[0].scrollTop += 600;", panel
                )
                time.sleep(1)
        except Exception:
            pass

        # Grab all listing cards
        cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK")[:max_results * 2]

        for card in cards:
            if len(results) >= max_results:
                break
            try:
                card.click()
                time.sleep(2)
                result = _extract_business_details(driver, query)
                if result and result["name"] not in [r["name"] for r in results]:
                    results.append(result)
                    print(f"  ✓ {result['name']} | {result['phone']} | {result['website']}")
            except Exception as e:
                continue

    except Exception as e:
        print(f"  ✗ Error scraping '{query}': {e}")

    return results


def _extract_business_details(driver, query: str) -> dict:
    """Extract details from an open business panel on Google Maps."""
    name, address, phone, website = "N/A", "N/A", "N/A", "N/A"

    try:
        # Business name
        try:
            name = driver.find_element(
                By.CSS_SELECTOR, "h1.DUwDvf, h1[class*='fontHeadlineLarge']"
            ).text.strip()
        except Exception:
            pass

        # Address
        try:
            addr_el = driver.find_element(
                By.CSS_SELECTOR,
                "button[data-item-id='address'], [data-tooltip='Copy address']"
            )
            address = addr_el.get_attribute("aria-label") or addr_el.text
            address = address.replace("Address: ", "").strip()
        except Exception:
            pass

        # Phone
        try:
            phone_el = driver.find_element(
                By.CSS_SELECTOR,
                "button[data-item-id^='phone'], [data-tooltip='Copy phone number']"
            )
            phone = phone_el.get_attribute("aria-label") or phone_el.text
            phone = phone.replace("Phone: ", "").strip()
        except Exception:
            pass

        # Website
        try:
            web_el = driver.find_element(
                By.CSS_SELECTOR,
                "a[data-item-id='authority'], a[aria-label*='website' i]"
            )
            website = web_el.get_attribute("href") or "N/A"
            # Clean up Google redirect URLs
            if "google.com/url" in website:
                parsed = urllib.parse.urlparse(website)
                params = urllib.parse.parse_qs(parsed.query)
                website = params.get("q", [website])[0]
        except Exception:
            pass

        # Infer industry from query
        industry = query.split(" in ")[0].title() if " in " in query else query.title()

        if name == "N/A":
            return None

        return {
            "name": name,
            "industry": industry,
            "address": address,
            "phone": phone,
            "website": website,
            "email": "N/A",
        }

    except Exception:
        return None


# ─────────────────────────────────────────────
#  MAIN RUNNER
# ─────────────────────────────────────────────

def run():
    print("\n" + "=" * 55)
    print("  BGH Distribution — Lead Scraper")
    print("  Plant Therapy Essential Oils | Malaysia & SG")
    print("=" * 55 + "\n")

    all_leads = []
    target = CONFIG["target_leads"]
    driver = None

    try:
        print("Starting browser...\n")
        driver = create_driver(headless=False)

        # Build search queries
        queries = []
        for biz in CONFIG["business_types"]:
            for city in CONFIG["cities"]:
                queries.append(f"{biz} in {city}")

        # Shuffle to vary results
        random.shuffle(queries)

        for query in queries:
            if len(all_leads) >= target:
                break

            print(f"\nSearching: {query}")
            leads = scrape_maps(
                driver, query,
                max_results=CONFIG["results_per_query"]
            )

            # De-duplicate by name
            existing_names = {l["name"].lower() for l in all_leads}
            for lead in leads:
                if lead["name"].lower() not in existing_names:
                    all_leads.append(lead)
                    existing_names.add(lead["name"].lower())

            print(f"  Total so far: {len(all_leads)}/{target}")
            time.sleep(CONFIG["delay_between_requests"])

    except KeyboardInterrupt:
        print("\n\nStopped by user.")
    finally:
        if driver:
            driver.quit()

    if not all_leads:
        print("\nNo leads collected. Try running again or check your internet connection.")
        return

    # Find emails
    if CONFIG["find_emails"] and all_leads:
        print(f"\n{'='*55}")
        print("Finding emails from websites...")
        print("=" * 55)
        for i, lead in enumerate(all_leads):
            if lead["website"] != "N/A":
                print(f"  [{i+1}/{len(all_leads)}] Checking {lead['name']}...")
                lead["email"] = find_email_from_website(lead["website"])
                print(f"         Email: {lead['email']}")
                time.sleep(CONFIG["delay_between_requests"])

    # Export to CSV
    output_path = CONFIG["output_file"]
    df = pd.DataFrame(all_leads, columns=[
        "name", "industry", "address", "phone", "website", "email"
    ])
    df.columns = ["Company Name", "Industry", "Address", "Phone", "Website", "Email"]
    df.to_csv(output_path, index=False)

    print(f"\n{'='*55}")
    print(f"  Done! {len(all_leads)} leads saved to: {output_path}")
    print(f"  Open the CSV, select all, copy, then paste into Google Sheets.")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    run()