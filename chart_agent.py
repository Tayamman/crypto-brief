"""Chart agent: pulls candles from Binance, computes indicators IN CODE,
then asks the AI to interpret the numbers (AI never eyeballs raw prices).

Run:  python chart_agent.py BTC ETH SOL
"""
import sys
from common import binance, dump
import brain


# ---------- indicators (pure Python, no pandas needed) ----------
def sma(vals, n):
    return sum(vals[-n:]) / n if len(vals) >= n else None


def ema_series(vals, n):
    k = 2 / (n + 1)
    out = [vals[0]]
    for v in vals[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(closes, n=14):
    if len(closes) <= n:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_g = sum(gains[:n]) / n
    avg_l = sum(losses[:n]) / n
    for i in range(n, len(gains)):  # Wilder smoothing
        avg_g = (avg_g * (n - 1) + gains[i]) / n
        avg_l = (avg_l * (n - 1) + losses[i]) / n
    if avg_l == 0:
        return 100.0
    return 100 - 100 / (1 + avg_g / avg_l)


def macd(closes):
    if len(closes) < 35:
        return None
    fast, slow = ema_series(closes, 12), ema_series(closes, 26)
    line = [a - b for a, b in zip(fast, slow)]
    signal = ema_series(line, 9)
    return {"macd": line[-1], "signal": signal[-1], "hist": line[-1] - signal[-1],
            "hist_prev": line[-2] - signal[-2]}


def bollinger(closes, n=20, mult=2):
    if len(closes) < n:
        return None
    w = closes[-n:]
    mid = sum(w) / n
    sd = (sum((x - mid) ** 2 for x in w) / n) ** 0.5
    return {"upper": mid + mult * sd, "mid": mid, "lower": mid - mult * sd}


def atr(highs, lows, closes, n=14):
    trs = []
    for i in range(1, len(closes)):
        trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]),
                       abs(lows[i] - closes[i - 1])))
    return sum(trs[-n:]) / n if len(trs) >= n else None


def swing_levels(highs, lows, look=5, keep=3):
    """Simple support/resistance from recent swing highs and lows."""
    res, sup = [], []
    for i in range(look, len(highs) - look):
        if highs[i] == max(highs[i - look:i + look + 1]):
            res.append(highs[i])
        if lows[i] == min(lows[i - look:i + look + 1]):
            sup.append(lows[i])
    price = None
    return res[-keep:], sup[-keep:]


# ---------- the agent ----------
def analyze(coin, interval="4h", limit=250):
    symbol = coin.upper() + "USDT"
    kl = binance("/api/v3/klines",
                 {"symbol": symbol, "interval": interval, "limit": limit})
    opens = [float(k[1]) for k in kl]
    highs = [float(k[2]) for k in kl]
    lows = [float(k[3]) for k in kl]
    closes = [float(k[4]) for k in kl]
    vols = [float(k[5]) for k in kl]
    price = closes[-1]

    sma20, sma50, sma200 = sma(closes, 20), sma(closes, 50), sma(closes, 200)
    m = macd(closes)
    bb = bollinger(closes)
    a = atr(highs, lows, closes)
    res, sup = swing_levels(highs, lows)
    avg_vol = sum(vols[-21:-1]) / 20

    facts = {
        "coin": coin.upper(),
        "interval": interval,
        "price": round(price, 6),
        "change_last_candle_pct": round((price / closes[-2] - 1) * 100, 2),
        "change_last_24_candles_pct": round((price / closes[-25] - 1) * 100, 2),
        "sma20": sma20, "sma50": sma50, "sma200": sma200,
        "price_vs_sma50": None if not sma50 else ("above" if price > sma50 else "below"),
        "price_vs_sma200": None if not sma200 else ("above" if price > sma200 else "below"),
        "rsi14": None if rsi(closes) is None else round(rsi(closes), 1),
        "macd": m,
        "bollinger": bb,
        "atr14": a,
        "atr_pct_of_price": None if not a else round(a / price * 100, 2),
        "recent_resistance": [round(x, 6) for x in res],
        "recent_support": [round(x, 6) for x in sup],
        "volume_vs_20_avg": round(vols[-1] / avg_vol, 2) if avg_vol else None,
        "high_of_range": max(highs[-100:]),
        "low_of_range": min(lows[-100:]),
    }
    return facts


def run(coins, intervals=("4h", "1d")):
    all_facts = []
    for c in coins:
        for iv in intervals:
            try:
                all_facts.append(analyze(c, iv))
            except Exception as e:  # noqa: BLE001
                all_facts.append({"coin": c, "interval": iv, "error": str(e)})
    task = (
        "For each coin, give: trend (up/down/range) across the two timeframes, "
        "momentum (RSI/MACD), key support and resistance, and one thing to watch. "
        "Flag anywhere the two timeframes disagree. Keep each coin to ~5 lines."
    )
    return brain.ask(task, dump(all_facts)), all_facts


if __name__ == "__main__":
    coins = sys.argv[1:] or ["BTC", "ETH", "SOL"]
    report, _ = run(coins)
    print(report)
