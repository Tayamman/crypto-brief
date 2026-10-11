"""News agent (free): RSS feeds + Fear & Greed index + CoinGecko trending.

Run:  python news_agent.py
"""
import re
import html
import xml.etree.ElementTree as ET
from common import get_text, get_json, dump
import brain

FEEDS = {
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Cointelegraph": "https://cointelegraph.com/rss",
    "Decrypt": "https://decrypt.co/feed",
    "Bitcoin Magazine": "https://bitcoinmagazine.com/feed",
}


def clean(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    return html.unescape(s).strip()


def fetch_feed(name, url, per_feed=8):
    items = []
    try:
        root = ET.fromstring(get_text(url))
    except Exception as e:  # noqa: BLE001
        return [{"source": name, "error": str(e)}]
    for it in root.iter("item"):
        items.append({
            "source": name,
            "title": clean(it.findtext("title")),
            "summary": clean(it.findtext("description"))[:240],
            "published": it.findtext("pubDate"),
            "link": it.findtext("link"),
        })
        if len(items) >= per_feed:
            break
    return items


def fear_greed():
    try:
        d = get_json("https://api.alternative.me/fng/", {"limit": 2})["data"]
        return {"now": f'{d[0]["value"]} ({d[0]["value_classification"]})',
                "yesterday": f'{d[1]["value"]} ({d[1]["value_classification"]})'}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def trending():
    try:
        d = get_json("https://api.coingecko.com/api/v3/search/trending")
        return [c["item"]["symbol"] for c in d["coins"]][:7]
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def run(focus=None):
    items = []
    for name, url in FEEDS.items():
        items += fetch_feed(name, url)
    good = [i for i in items if "error" not in i]
    if focus:
        f = focus.lower()
        good = [i for i in good if f in (i["title"] + i["summary"]).lower()] or good
    data = {"fear_and_greed": fear_greed(), "trending_on_coingecko": trending(),
            "headlines": good[:30]}
    task = (
        "Write a NEWS BRIEF: (1) Top 5 stories that could actually move markets, "
        "each with one line on why it matters, (2) overall sentiment and the Fear & Greed "
        "reading, (3) coins being talked about. Skip fluff and duplicates. "
        "Mention the source name for each story."
    )
    return brain.ask(task, dump(data)), data


if __name__ == "__main__":
    report, _ = run()
    print(report)
