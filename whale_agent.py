"""Whale agent (100% free, Binance public data).

How it finds 'whale' money without paid APIs:
  1. Scans the top coins by 24h USDT volume (stablecoins excluded).
  2. For each, reads several pages of recent trades and keeps only BIG ones
     (>= WHALE_USD, default $50k) and sums net buying vs net selling.
  3. Also reads hourly candles' taker-buy volume: if aggressive buyers
     dominate, money is flowing in even when single trades are small.

Honest limits: this sees Binance spot only, over a short recent window
(the report states the window per coin). It is a hint of where large money
is moving, not proof of who is behind it.

Run:  python whale_agent.py
"""
import os
from common import binance, money, dump
import brain

WHALE_USD = float(os.getenv("WHALE_USD", "50000"))
TOP_N = int(os.getenv("WHALE_TOP_N", "25"))
PAGES = int(os.getenv("WHALE_PAGES", "3"))  # x1000 trades per coin
STABLES = {"USDC", "FDUSD", "TUSD", "USDP", "DAI", "USDE", "BUSD", "EUR", "TRY",
           "RLUSD", "USD1", "PYUSD", "USDS", "USDD", "AEUR", "BFUSD", "XUSD",
           "USDT", "UST", "GUSD", "FRAX", "LUSD", "EURI"}


def looks_like_stable(base, price, chg):
    return base in STABLES or (0.97 <= price <= 1.03 and abs(chg) < 0.3)


def top_pairs(n=TOP_N):
    tickers = binance("/api/v3/ticker/24hr")
    rows = []
    for t in tickers:
        s = t["symbol"]
        if not s.endswith("USDT"):
            continue
        base = s[:-4]
        price = float(t["lastPrice"])
        chg = float(t["priceChangePercent"])
        if base.endswith(("UP", "DOWN")) or looks_like_stable(base, price, chg):
            continue
        rows.append({"symbol": s, "coin": base,
                     "quote_vol": float(t["quoteVolume"]),
                     "chg_24h": chg, "price": price})
    rows.sort(key=lambda r: r["quote_vol"], reverse=True)
    return rows[:n]


def recent_trades(symbol, pages=PAGES):
    """Latest ~1000*pages trades, paging backwards by trade id."""
    batch = binance("/api/v3/aggTrades", {"symbol": symbol, "limit": 1000})
    trades = list(batch)
    for _ in range(pages - 1):
        if not batch:
            break
        first_id = batch[0]["a"]
        start = max(first_id - 1000, 0)
        if start == first_id:
            break
        batch = binance("/api/v3/aggTrades",
                        {"symbol": symbol, "fromId": start, "limit": 1000})
        batch = [t for t in batch if t["a"] < first_id]
        trades = batch + trades
    return trades


def big_trade_flow(symbol):
    """Net flow from large trades among the most recent trades."""
    trades = recent_trades(symbol)
    buy = sell = 0.0
    nbig = 0
    biggest = 0.0
    for t in trades:
        usd = float(t["p"]) * float(t["q"])
        if usd < WHALE_USD:
            continue
        nbig += 1
        biggest = max(biggest, usd)
        # m == True means the buyer was the maker -> aggressor was a SELLER
        if t["m"]:
            sell += usd
        else:
            buy += usd
    window_min = None
    if trades and "T" in trades[0] and "T" in trades[-1]:
        window_min = round((trades[-1]["T"] - trades[0]["T"]) / 60000, 1)
    return {"big_buy": buy, "big_sell": sell, "net": buy - sell,
            "big_trade_count": nbig, "biggest_trade": biggest,
            "window_minutes": window_min, "trades_read": len(trades)}


def taker_pressure(symbol, hours=24):
    """Taker-buy share of volume over the last N hours (0.5 = balanced)."""
    kl = binance("/api/v3/klines",
                 {"symbol": symbol, "interval": "1h", "limit": hours})
    quote = sum(float(k[7]) for k in kl)
    taker_buy_quote = sum(float(k[10]) for k in kl)
    if quote == 0:
        return None, 0
    share = taker_buy_quote / quote
    net = taker_buy_quote - (quote - taker_buy_quote)  # buy minus sell, in USD
    return round(share, 3), net


def scan():
    rows = []
    for p in top_pairs():
        try:
            flow = big_trade_flow(p["symbol"])
            share, net24 = taker_pressure(p["symbol"])
        except Exception as e:  # noqa: BLE001
            rows.append({"coin": p["coin"], "error": str(e)})
            continue
        rows.append({
            "coin": p["coin"],
            "price": p["price"],
            "chg_24h_pct": round(p["chg_24h"], 2),
            "volume_24h": money(p["quote_vol"]),
            "window_minutes_covered": flow["window_minutes"],
            "whale_buy_recent": money(flow["big_buy"]),
            "whale_sell_recent": money(flow["big_sell"]),
            "whale_net_recent_usd": round(flow["net"]),
            "whale_net_recent": money(flow["net"]),
            "big_trades": flow["big_trade_count"],
            "biggest_trade": money(flow["biggest_trade"]),
            "taker_buy_share_24h": share,
            "taker_net_24h": money(net24),
            "taker_net_24h_usd": round(net24),
        })
    return rows


def run():
    rows = [r for r in scan() if "error" not in r]
    active = [r for r in rows if r["big_trades"] > 0]
    quiet = [r["coin"] for r in rows if r["big_trades"] == 0]
    by_whale = sorted(active, key=lambda r: r["whale_net_recent_usd"], reverse=True)
    by_taker = sorted(rows, key=lambda r: r["taker_net_24h_usd"], reverse=True)
    summary = {
        "whale_threshold": f">= {money(WHALE_USD)} per trade",
        "note": ("whale_* fields cover only the recent window shown in "
                 "window_minutes_covered; taker_* fields cover 24h."),
        "top_whale_buying_recent": [r for r in by_whale if r["whale_net_recent_usd"] > 0][:5],
        "top_whale_selling_recent": [r for r in by_whale[::-1] if r["whale_net_recent_usd"] < 0][:5],
        "coins_with_no_large_trades_in_window": quiet,
        "strongest_taker_buying_24h": by_taker[:5],
        "strongest_taker_selling_24h": by_taker[-5:][::-1],
        "coins_scanned": len(rows),
    }
    task = (
        "Write a WHALE REPORT. Sections: (1) Where big money is buying, "
        "(2) Where it is selling, (3) Divergences (e.g. heavy taker buying while price "
        "falls, or whale selling while price rises), (4) One-line takeaway. "
        "Treat the 24h taker flow as the broad signal and the whale-trade fields as a "
        "short recent snapshot. If a list is empty, say no large trades were seen. "
        "Mention this is Binance spot only and state the whale threshold. "
        "Do not overstate certainty."
    )
    return brain.ask(task, dump(summary)), summary


if __name__ == "__main__":
    report, _ = run()
    print(report)
