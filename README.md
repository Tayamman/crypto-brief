# Free Crypto AI Agents

Three agents plus a boss script. Total cost: $0.

| Agent | File | Data source (free) |
|---|---|---|
| Chart analyst | `chart_agent.py` | Binance public candles, indicators computed in code |
| Whale tracker | `whale_agent.py` | Binance big trades and taker-buy pressure |
| News reader | `news_agent.py` | CoinDesk, Cointelegraph, Decrypt, Bitcoin Magazine RSS, Fear & Greed, CoinGecko trending |
| Boss | `daily_brief.py` | Runs all three and merges one brief |

The AI "brain" is Google Gemini's free tier.

## Setup (5 minutes)

1. Install Python 3.10+ from python.org.
2. In this folder run: `pip install -r requirements.txt`
3. Get a free Gemini key (no card): https://aistudio.google.com/apikey
4. Copy `.env.example` to `.env` and paste the key after `GEMINI_API_KEY=`

## Run

```
python chart_agent.py BTC ETH SOL
python whale_agent.py
python news_agent.py
python daily_brief.py BTC ETH SOL XRP
```

Reports are saved in `reports/`. Without a Gemini key, the agents still run and print the raw data.

## Run it automatically for free

**Option A, GitHub Actions (computer can be off):**
1. Put this folder in a GitHub repo (free account).
2. Repo Settings > Secrets and variables > Actions > add `GEMINI_API_KEY` (and the Telegram ones if used).
3. `.github/workflows/daily.yml` runs the brief every day at 08:00 Pakistan time. Edit the cron to change it.
   Download results from the Actions run, or get them on Telegram.

**Option B, your own PC:** Windows Task Scheduler running `python daily_brief.py`.

## Phone delivery (free)

Fill in the two Telegram values in `.env`. The brief arrives as a message.

## Known limits (be honest with yourself)

- Whale data is Binance spot only and covers a short recent window. It shows where large orders are hitting, not who the wallet is.
- Indicators describe the past. Nothing here predicts price, and none of it is financial advice.
- Free tiers have rate limits. If Gemini says "quota", wait a minute and retry.
- If Binance is blocked in your network, the code tries a second mirror. A VPN may be needed if both fail.

## Upgrades later (still free)

- On-chain whales: Etherscan free API (large ETH/token transfers), Whale Alert free tier.
- Hyperliquid public API for large perp positions.
- Alerts only when something unusual happens (instead of a daily report).
- Backtest any rule you believe in before risking money.
