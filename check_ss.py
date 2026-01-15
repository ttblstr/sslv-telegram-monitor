import os
import json
import re
import html
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
    "Accept-Language": "lv-LV,lv;q=0.9",
}


def load_seen() -> set[str]:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set[str]) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=2)


def send_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(
        url,
        json={"chat_id": CHAT_ID, "text": text},
        timeout=20,
    ).raise_for_status()


def clean_text(text: str) -> str:
    """Remove HTML and normalize whitespace."""
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)  # strip HTML tags
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def extract_price(text: str) -> int | None:
    """
    Extracts EUR price from text.
    Accepts: '295 000 €', '295000 EUR'
    Rejects: missing price, negotiable, garbage.
    """
    if not text:
        return None

    t = text.lower()
    if "vienošan" in t or "pēc vienošanās" in t:
        return None

    # Strict EUR match only
    m = re.search(r"(\d{2,3}(?:\s?\d{3})?)\s*(€|eur)", text, re.IGNORECASE)
    if not m:
        return None

    price = int(m.group(1).replace(" ", ""))
    return price if price > 0 else None


def fetch_rss(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def parse_rss(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel") or root.find(".//channel")

    items = []
    for item in channel.findall("item"):
        title = clean_text(item.findtext("title") or "")
        link = (item.findtext("link") or "").strip()
        desc = clean_text(item.findtext("description") or "")
        guid = (item.findtext("guid") or "").strip()

        key = link or guid
        if not key:
            continue

        items.append(
            {
                "title": title,
                "link": link,
                "desc": desc,
                "key": key,
            }
        )
    return items


def check_location(location: str, rss_url: str, seen: set[str]) -> None:
    xml = fetch_rss(rss_url)
    items = parse_rss(xml)

    for it in items:
        key = it["key"]
        if key in seen:
            continue

        seen.add(key)

        price = extract_price(f"{it['title']} {it['desc']}")
        if price is None or price > MAX_PRICE:
            continue

        message = (
            f"🏠 {it['title']}\n"
            f"📍 {location}\n"
            f"💰 {price} €\n"
            f"🔗 {it['link']}"
        )

        send_message(message)


def main() -> None:
    seen = load_seen()
    for location, rss_url in URLS.items():
        check_location(location, rss_url, seen)
    save_seen(seen)


if __name__ == "__main__":
    main()
