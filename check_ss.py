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
    requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=20).raise_for_status()


def extract_price_eur(text: str) -> int | None:
    """
    Finds something like '250 000 €' or '250000 EUR' anywhere in the RSS item.
    Returns int euros or None if not found / not numeric.
    """
    if not text:
        return None
    m = re.search(r"(\d[\d\s]{2,})\s*(?:€|eur)\b", text, flags=re.IGNORECASE)
    if not m:
        return None
    digits = re.sub(r"\s+", "", m.group(1))
    return int(digits) if digits.isdigit() else None


def fetch_rss(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def parse_rss_items(xml_text: str) -> list[dict]:
    """
    Parses RSS 2.0-ish feeds.
    Returns list of dicts: {title, link, description}
    """
    root = ET.fromstring(xml_text)

    # RSS2: <rss><channel><item>...
    channel = root.find("channel")
    if channel is None:
        # Sometimes namespace-wrapped; fall back to searching
        channel = root.find(".//channel")

    items = []
    for item in channel.findall("item") if channel is not None else root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        guid = (item.findtext("guid") or "").strip()

        # use guid if link missing
        url_key = link or guid
        if not url_key:
            continue

        items.append({"title": title, "link": link, "desc": desc, "key": url_key})
    return items


def check_location(location: str, rss_url: str, seen: set[str]) -> None:
    xml_text = fetch_rss(rss_url)
    items = parse_rss_items(xml_text)

    for it in items:
        key = it["key"]
        link = it["link"] or it["key"]

        if key in seen:
            continue

        # Try to extract price from title+description
        price = extract_price_eur(f"{it['title']} {it['desc']}")
        if price is None or price > MAX_PRICE:
            # If no numeric price, ignore (e.g. "cena pēc vienošanās")
            seen.add(key)  # still mark as seen to avoid re-processing forever
            continue

        msg = (
            f"🏠 {it['title']}\n"
            f"📍 {location}\n"
            f"💰 {price} €\n"
            f"🔗 {link}"
        )
        send_message(msg)
        seen.add(key)


def main() -> None:
    seen = load_seen()
    for location, rss_url in URLS.items():
        check_location(location, rss_url, seen)
    save_seen(seen)


if __name__ == "__main__":
    main()
