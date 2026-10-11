"""Boss script: runs all three agents, merges them into ONE brief,
saves it to reports/, opens it in your browser as a clean page, and
(optionally) sends it to your phone.

Run:  python daily_brief.py
      python daily_brief.py BTC ETH SOL XRP     (choose coins for the chart agent)

Set AUTO_OPEN=0 in .env if you don't want the page to open by itself.
"""
import sys
import chart_agent
import whale_agent
import news_agent
import brain
import report_html
from common import save_report, notify, now_utc


def main():
    coins = sys.argv[1:] or ["BTC", "ETH", "SOL"]
    print("Running news agent...")
    news, _ = news_agent.run()
    print("Running whale agent...")
    whales, _ = whale_agent.run()
    print("Running chart agent...")
    charts, _ = chart_agent.run(coins)

    task = (
        "Merge these three agent reports into ONE morning brief, max ~400 words. "
        "Order: Market mood, Whales, Charts, News, then 'What to watch today'. "
        "Point out where the agents agree or conflict. No financial advice."
    )
    combined = f"NEWS:\n{news}\n\nWHALES:\n{whales}\n\nCHARTS:\n{charts}"
    merged = brain.ask(task, combined)

    now = now_utc()
    stamp = now.strftime("%Y-%m-%d %H:%M UTC")
    full = (f"# Crypto Brief, {stamp}\n\n{merged}\n\n---\n\n"
            f"## Detail: Whales\n{whales}\n\n## Detail: Charts\n{charts}\n\n"
            f"## Detail: News\n{news}\n")
    path = save_report("brief", full)
    print("\n" + merged)
    print(f"\nSaved: {path}")

    page = report_html.build_html(
        title="Crypto Brief",
        subtitle=f"{stamp}  |  charts: {', '.join(c.upper() for c in coins)}",
        top_md=merged,
        details=[("Whale details", whales), ("Chart details", charts),
                 ("News details", news)],
    )
    html_path, opened = report_html.save_and_open(
        page, "brief_" + now.strftime("%Y-%m-%d_%H%M"))
    print(f"Page: {html_path}" + ("  (opened in your browser)" if opened else
          "  (open reports/latest.html to read it)"))

    sent = notify(f"Crypto Brief, {stamp}\n\n{merged}")
    if sent:
        print("Sent to: " + ", ".join(sent))


if __name__ == "__main__":
    main()
