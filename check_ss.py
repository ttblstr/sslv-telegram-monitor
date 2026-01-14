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
    # NOTE: if any of these 3 slugs is wrong, the debug message will show 0 items and the HTTP status.
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
    More tolerant price extractor:
    - accepts '250 000', '250000', with/without € or EUR
    - ignores 'cena pēc vienošanās' / non-numeric
    - returns int or None
    """
    if not text:
        return None

    t = text.lower()

    # If it's explicitly "negotiable" in Latvian/Russian, don't try
    if "vienošan" in t or "dogovor" in t or "договор" in t:
        return None

    # First try patterns with currency
    m = re.search(r"(\d[\d\s]{2,})\s*(€|eur)\b", text, flags=re.IGNORECASE)
    if m:
        digits = re.sub(r"\s+", "", m.group(1))
        if digits.isdigit():
            return int(digits)

    # Fallback: pick a "big-looking" number (e.g., 250000 or 250 000) from title/desc
    # We only accept >= 10000 to avoid matching room counts etc.
    candidates = re.findall(r"\d[\d\s]{3,}", text)
    best = None
    for c in candidates:
        digits = re.sub(r"\s+", "", c)
        if digits.isdigit():
            val = int(digits)
            if val >= 10000:
                # keep the first plausible, or the largest plausible
                best = val if best is None else max(best, val)
    return best


def fetch_rss(url: str) -> tuple[int, str]:
    r = requests.get(url, headers=HEADERS, timeout=30)
    return r.status_code, r.text


def parse_rss_items(xml_text: str) -> list[dict]:
    # Ensure it's XML and contains items
    root = ET.fromstring(xml_text)

    # Standard RSS: <rss><channel><item>...</item></channel></rss>
    channel = root.find("channel") or root.find(".//channel")
    item_nodes = channel.findall("item") if channel is not None else root.findall(".//item")

    items = []
    for item in item_nodes:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        key = link or guid or title  # last resort

        if not key:
            continue

        items.append({"title": title, "link": link, "desc": desc, "key": key})
    return items


def check_location(location: str, rss_url: str, seen: set[str]) -> tuple[int, int]:
    status, xml_text = fetch_rss(rss_url)

    # If URL is wrong or blocked, ET.fromstring will fail -> we want to see it
    items = parse_rss_items(xml_text)

    new_seen = 0
    sent = 0

    for it in items:
        key = it["key"]
        link = it["link"] or it["key"]

        if key in seen:
            continue

        price = extract_price_any(f"{it['title']} {it['desc']}")
        seen.add(key)
        new_seen += 1

        if price is None or price > MAX_PRICE:
            continue

        msg = (
            f"🏠 {it['title']}\n"
            f"📍 {location}\n"
            f"💰 {price} €\n"
            f"🔗 {link}"
        )
        send_message(msg)
        sent += 1

    return status, len(items)


def main() -> None:
    seen = load_seen()

    # One run summary (sends ONE message per run so you can confirm it works)
    summaries = []
    for location, rss_url in URLS.items():
        try:
            status, count = check_location(location, rss_url, seen)
            summaries.append(f"{location}: HTTP {status}, items {count}")
        except Exception as e:
            summaries.append(f"{location}: ERROR {type(e).__name__}")

    save_seen(seen)

    # TEMPORARY: Keep this for 1-2 runs, then remove if you want silence.
    send_message("✅ SS.lv RSS check finished:\n" + "\n".join(summaries))


if __name__ == "__main__":
    main()
