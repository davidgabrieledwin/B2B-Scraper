# B2B Lead Scraper (X Distribution)

A Python script that finds potential B2B customers on Google Maps for X Distribution, the sole distributor of X essential oils in Malaysia and Singapore. It replaces manual searching, copy-pasting and duplicate-checking before WhatsApp outreach.

Built with AI assistance (Claude) and iterated from v1 to v3 against real Google Maps results.

## What it does

1. Searches Google Maps across 84 Malaysian towns and cities plus Singapore for four sectors: Spa, Soap Manufacturer, Perfume Manufacturer and Traditional Chinese Medicine (TCM).
2. Opens each listing and extracts company name, phone and website.
3. Applies the filters below.
4. Scans each company's website (homepage and common contact pages) for an email address.
5. Exports one CSV with: Company Name, Industry, Email, Phone / WhatsApp, Website / Social.

## Rules the code applies

| Rule | Behaviour |
|---|---|
| Duplicates | Skips companies already in `existing_leads.csv`; the match ignores suffixes such as Sdn Bhd / Pte Ltd |
| Large brands | Skips well-known multinationals and retailers (keyword list in the script) |
| WhatsApp-capable numbers | Detects Malaysian (01x) and Singapore (+65 8/9) mobiles. Office numbers are kept, with a console warning (not flagged in the CSV) |
| Quota | Stops each sector at 15 leads (60 total by default). If queries run out first, the end summary marks that sector with a warning |
| Minimum contact | Needs a phone or email at collection time. Emails are looked up afterwards, so in practice a phone number. A website is optional |

## Requirements

- Python 3.9+
- Google Chrome installed
- `pip install selenium webdriver-manager requests beautifulsoup4 pandas`

## Usage

1. Export your Google Sheet as CSV and rename it `existing_leads.csv`.
2. Put it in the same folder as `Scraper.py`.
3. Run `python Scraper.py`. A Chrome window opens and works through the searches.
4. Open the generated `BGH_Leads_v3_<date>.csv` and paste it into your Google Sheet.

Settings (results per query, delay, email lookup, output name) are in the `CONFIG` block at the top of the script.

## Known limitations

- Google Maps changes its page structure often; the CSS selectors may need updating.
- Maps mostly lists landlines, so many leads will not have a WhatsApp-capable number.
- Email lookup only checks the homepage and a few common contact pages.
- `CONFIG["total_target"]` is defined but not used.

## Responsible use

- Scraping Google Maps may breach Google's Terms of Service. Use it for low-volume, internal research only.
- Business phone numbers can be personal data (Malaysia PDPA, Singapore PDPA). Singapore's Do Not Call registry also covers marketing messages. Check the rules before messaging.
- Lead data stays out of this repo (see `.gitignore`): do not commit `existing_leads.csv` or any `BGH_Leads_*.csv`.
