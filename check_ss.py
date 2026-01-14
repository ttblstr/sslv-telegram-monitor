import requests
import os
import json
import re
from bs4 import BeautifulSoup

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
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(list(seen)), f)


def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=10)


def extract_price(text):
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return None
    return int(digits)


def check_location(location, url, seen):
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10)",
        "Accept-Language": "lv-LV,lv;q=0.9",
    }

    r = requests.get(url, headers=headers, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("div.list_item")

    for item in items:
        a = item.find("a", href=True)
        if not a or "/msg/" not in a["href"]:
            continue

        link = "https://www.ss.lv" + a["href"]
        if link in seen:
            continue

        title = a.get_text(strip=True)

        price_div = item.find("div", class_="price")
        if not price_div:
            continue

        price = extract_price(price_div.get_text())
        if not price or price > MAX_PRICE:
            continue

        message = (
            f"🏠 {title}\n"
            f"📍 {location}\n"
            f"💰 {price} €\n"
            f"🔗 {link}"
        )

        send_message(message)
        seen.add(link)


def main():
    seen = load_seen()

    for location, url in URLS.items():
        check_location(location, url, seen)

    save_seen(seen)


if __name__ == "__main__":
    main()
