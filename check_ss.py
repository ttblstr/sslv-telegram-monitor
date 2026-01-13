import requests
import os
import json
from bs4 import BeautifulSoup

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

MAX_PRICE = 300000
STATE_FILE = "seen.json"

URLS = {
    "Mārupes pag.": "https://www.ss.lv/lv/real-estate/homes-summer-residences/riga-region/marupe-parish/sell/",
    "Āgenskalns": "https://www.ss.lv/lv/real-estate/homes-summer-residences/riga/agenskalns/sell/",
    "Bieriņi": "https://www.ss.lv/lv/real-estate/homes-summer-residences/riga/bierini/sell/",
}


def load_seen():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(list(seen), f)


def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=10)


def parse_price(text):
    try:
        return int(text.replace("€", "").replace(" ", "").strip())
    except:
        return None


def check_location(location, url, seen):
    headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "lv-LV,lv;q=0.9,en-US;q=0.8,en;q=0.7",
}

r = requests.get(url, headers=headers, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")

    rows = soup.select("tr[id^='tr_']")
    for row in rows:
        a = row.select_one("a")
        tds = row.find_all("td")

        if not a or len(tds) < 5:
            continue

        link = "https://www.ss.lv" + a["href"]
        if link in seen:
            continue

        price = parse_price(tds[-1].text)
        if not price or price > MAX_PRICE:
            continue

        title = a.text.strip()

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

