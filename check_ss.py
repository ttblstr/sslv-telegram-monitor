import requests
import os
import json
import re
from bs4 import BeautifulSoup

# ================= CONFIG =================

BOT_TOKEN = os.environ["BOT_TOKEN"].strip()
CHAT_ID = os.environ["CHAT_ID"].strip()

MAX_PRICE = 300000
STATE_FILE = "seen.json"

URLS = {
    "Mārupes pag.": "https://www.ss.lv/lv/real-estate/homes-summer-residences/riga-region/marupes-pag/sell/",
    "Āgenskalns": "https://www.ss.lv/lv/real-estate/homes-summer-residences/riga/agenskalns/sell/",
    "Bieriņi": "https://www.ss.lv/lv/real-estate/homes-summer-residences/riga/bierini/sell/",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "lv-LV,lv;q=0.9,en;q=0.8",
}

# ================= HELPERS =================

def log(msg):
    print(msg, flush=True)

def load_seen():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(seen), f)

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(
        url,
        json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True},
        timeout=15,
    )
    r.raise_for_status()

def extract_price(text):
    """
    Extract integer price from text like:
    '295 000 €', '300000 EUR', etc.
    """
    if not text:
        return None
    m = re.search(r"(\d[\d\s]{3,})", text)
    if not m:
        return None
    return int(m.group(1).replace(" ", ""))

# ================= CORE =================

def check_location(location, url, seen):
    log(f"\n--- Checking {location} ---")
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    rows = soup.find_all("tr")

    log(f"Rows found: {len(rows)}")

    found_any = False

    for row in rows:
        link_tag = row.find("a", href=True)
        if not link_tag:
            continue

        href = link_tag["href"]
        if not href.startswith("/msg/"):
            continue

        full_link = "https://www.ss.lv" + href
        if full_link in seen:
            continue

        cols = row.find_all("td")
        price = None

        for col in cols:
            p = extract_price(col.get_text(strip=True))
            if p:
                price = p
                break

        if price is None:
            continue

        if price > MAX_PRICE:
            continue

        title = link_tag.get_text(strip=True)

        message = (
            f"🏠 {title}\n"
            f"📍 {location}\n"
            f"💰 {price} €\n"
            f"🔗 {full_link}"
        )

        log(f"SENDING: {title} | {price}")
        send_message(message)

        seen.add(full_link)
        found_any = True

    if not found_any:
        log("No new matching listings.")

# ================= ENTRY =================

def main():
    log("=== SS.LV MONITOR START ===")
    seen = load_seen()

    for location, url in URLS.items():
        check_location(location, url, seen)

    save_seen(seen)
    log("=== DONE ===")

if __name__ == "__main__":
    main()