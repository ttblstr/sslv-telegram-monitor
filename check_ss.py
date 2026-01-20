import os
import json
import re
import requests
import xml.etree.ElementTree as ET

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

MAX_PRICE = 300000
STATE_FILE = "seen.json"

URLS = {
    "Mārupes pag.": "https://www.ss.lv/lv/real-estate/homes-summer-residences/riga-region/marupes-pag/sell/rss/",
    "Āgenskalns": "https://www.ss.lv/lv/real-estate/homes-summer-residences/riga/agenskalns/sell/rss/",
    "Bieriņi": "https://www.ss.lv/lv/real-estate/homes-summer-residences/riga/bierini/sell/rss/",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "lv-LV,lv;q=0.9,en-US;q=0.8,en;q=0.7",
}


def load_seen():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=2)


def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=20)
    r.raise_for_status()


def extract_price(text):
    if not text:
        return None

    text_l = text.lower()
    if "vienošan" in text_l:
        return None

    m = re.search(r"(\d[\d\s]{3,})\s*(€|eur)?", text, re.IGNORECASE)
    if not m:
        return None

    digits = re.sub(r"\s+", "", m.group(1))
    if not digits.isdigit():
        return None

    value = int(digits)
    return value if value >= 10000 else None


def fetch_rss(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def parse_items(xml_text):
    root = ET.fromstring(xml_text)
    channel = root.find("channel") or root.find(".//channel")
    items = []

    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        key = link or title

        items.append({
            "title": title,
            "link": link,
            "desc": desc,
            "key": key,
        })

    return items


def check_location(location, rss_url, seen):
    xml = fetch_rss(rss_url)
    items = parse_items(xml)

    for it in items:
        if it["key"] in seen:
            continue

        seen.add(it["key"])

        price = extract_price(it["title"] + " " + it["desc"])
        if price is None or price > MAX_PRICE:
            continue

        msg = (
            f"🏠 {it['title']}\n"
            f"📍 {location}\n"
            f"💰 {price} €\n"
            f"🔗 {it['link']}"
        )
        send_message(msg)


def main():
    seen = load_seen()

    for location, url in URLS.items():
        check_location(location, url, seen)

    save_seen(seen)


if __name__ == "__main__":
    main()