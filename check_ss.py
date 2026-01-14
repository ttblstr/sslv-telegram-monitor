import requests
import os
import json
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

MAX_PRICE = 300000
STATE_FILE = "seen.json"

URLS = {
    "Mārupes pag.": "https://m.ss.lv/lv/real-estate/homes-summer-residences/riga-region/marupes-pag/sell/",
    "Āgenskalns": "https://m.ss.lv/lv/real-estate/homes-summer-residences/riga/agenskalns/sell/",
    "Bieriņi": "https://m.ss.lv/lv/real-estate/homes-summer-residences/riga/bierini/sell/",
}


def load_seen():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            print(f"Error loading seen.json: {e}")
    return set()


def save_seen(seen):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(seen)), f, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving seen.json: {e}")


def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
        "parse_mode": "HTML"  # optional: makes links prettier
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"Telegram send failed: {e}")


def extract_price(text):
    if not text:
        return None
    # Remove everything except digits and keep last possible price-like part
    cleaned = re.sub(r'[^\d\s€]', '', text)
    matches = re.findall(r'\d{1,3}(?:\s*\d{3})*(?:\s*€)?', cleaned)
    if not matches:
        return None
    # Take the last number sequence (usually the actual price)
    last = matches[-1].replace(' ', '').replace('€', '')
    try:
        return int(last)
    except ValueError:
        return None


def check_location(location, url, seen):
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
        "Accept-Language": "lv-LV,lv;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch {location} ({url}): {e}")
        return

    soup = BeautifulSoup(r.text, "html.parser")

    print(f"DEBUG {location}: Total <tr> tags: {len(soup.find_all('tr'))}")
    print(f"DEBUG {location}: tr[id^='tr_']: {len(soup.select(\"tr[id^='tr_']\"))}")
    print(f"DEBUG {location}: div.am: {len(soup.select('div.am'))}")
    print(f"DEBUG {location}: div.msg: {len(soup.select('div.msg'))}")
    print(f"DEBUG {location}: Elements with a[href*='/msg/']: {len(soup.select(\"a[href*='/msg/']\"))}")
    print(f"DEBUG {location}: Parent containers of /msg/ links (approx): {len(soup.select(\"div:has(a[href*='/msg/'])\")) or 'N/A (needs lxml parser)'}")
    
    # Main listing rows on m.ss.lv — table rows with id="tr_*"
    rows = soup.select('tr[id^="tr_"]')

    if not rows:
        print(f"Warning: No listing rows found for {location}. Selector may need update. Found {len(soup.select('tr'))} <tr> tags total.")
        # Optional fallback attempt
        rows = soup.select("div.am") or soup.select("div.msg") or soup.find_all("tr")

    new_items = 0

    for row in rows:
        # Skip header / separator rows
        if 'msga_head' in row.get('class', []) or not row.get('id', '').startswith('tr_'):
            continue

        a = row.find("a", href=True)
        if not a or "/msg/" not in a["href"]:
            continue



