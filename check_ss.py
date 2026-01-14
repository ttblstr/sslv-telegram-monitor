import os
import json
import re
import requests
import xml.etree.ElementTree as ET

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

MAX_PRICE = 300000
STATE_FILE = "seen.json"

# Your 3 monitored SS.lv RSS feeds (confirmed working: HTTP 200, items > 0)
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


def extract_price_any(text: str) -> int | None:
    """
    Extract a plausible EUR price from text.

    Handles:
      - "250 000 €", "250000 €", "250 000 EUR"
      - Fallback to a large number if currency is omitted in RSS
    Ignores:
      - "cena pēc vienošanās" / negotiable text
    """
    if not text:
        return None

    t = text.lower()
    if "vienošan" in t or "dogovor" in t or "договор" in t:
        return None

    # Prefer explicit currency patterns
    m = re.search(r"(\d[\d\s]{2,})\s*(€|eur)\b", text, flags=re.IGNORECASE)
    if m:
        digits = re.sub(r"\s+", "", m.group(1))
        if digits.isdigit():
            return int(digits)

    # Fallback: any "big-looking" number (>= 10k) to avoid matching room counts etc.
    candidates = re.findall(r"\d[\d\s]{3,}", text)
    best = None
    for c in candidates:
        digits = re.sub(r"\s+", "", c)
        if digits.isdigit():
            val = int(digits)
            if val >= 10000:
                best = val if best is None else max(best, val)

    return best


def fetch_rss(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def parse_rss_items(xml_text: str) -> list[dict]:
    """
    Parse RSS (RSS 2.0-ish).
    Returns list of dicts: {title, link, desc, key}
    """
    root = ET.fromstring(xml_text)

    # Typical RSS: <rss><channel><item>...</item></channel></rss>
    channel = root.find("channel") or root.find(".//channel")
    item_nodes = channel.findall("item") if channel is not None else root.findall(".//item")

    items: list[dict] = []
    for item in item_nodes:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        guid = (item.findtext("guid") or "").strip()

        # Stable key so we don't reprocess the same listing
        key = link or guid or title
        if not key:
            continue

        items.append({"title": title, "link": link, "desc": desc, "key": key})
    return items


def check_location(location: str, rss_url: str, seen: set[str]) -> None:
    xml_text = fetch_rss(rss_url)
    items = parse_rss_items(xml_text)

    for it in items:
        key = it["key"]
        link = it["link"] or it["key"]

        if key in seen:
            continue

        # Mark as seen immediately to avoid repeated processing even if filtered out
        seen.add(key)

        # Price filter (<= 300k)
        price = extract_price_any(f"{it['title']} {it['desc']}")
        if price is None or price > MAX_PRICE:
            continue

        msg = (
            f"🏠 {it['title']}\n"
            f"📍 {location}\n"
            f"💰 {price} €\n"
            f"🔗 {link}"
        )
        send_message(msg)


def main() -> None:
    seen = load_seen()

    for location, rss_url in URLS.items():
        check_location(location, rss_url, seen)

    save_seen(seen)


if __name__ == "__main__":
    main()
