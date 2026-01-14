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


def extract_price(text: str) -> int | None:
    if not text:
        return None

    t = text.lower()
    if "vienošan" in t:
        return None

    m = re.search(r"(\d[\d\s]{2,})\s*(€|eur)", text, re.IGNORECASE)
    if m:
        return int(re.sub(r"\s+", "", m.group(1)))

    nums = re.findall(r"\d[\d\s]{4,}", text)
    for n in nums:
        val = int(re.sub(r"\s+", "", n))
        if val >= 10000:
            return val

    return None


def fetch_rss(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def parse_rss(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel") or root.find(".//channel")
    items = []

    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
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


send_message("✅ Bot is alive and monitoring")


def main() -> None:
    seen = load_seen()
    for location, rss_url in URLS.items():
        check_location(location, rss_url, seen)
    save_seen(seen)


if __name__ == "__main__":
    main()
