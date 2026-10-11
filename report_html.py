"""Turns the brief (markdown-ish text from the AI) into a clean, self-contained
HTML page and opens it in your browser. No extra libraries needed."""
import os
import re
import html
import webbrowser
from pathlib import Path

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--text:#1b1f24;--muted:#667085;--line:#e4e7ec;--accent:#2563eb}
@media (prefers-color-scheme:dark){:root{--bg:#0e1116;--card:#161b22;--text:#e6e9ee;--muted:#8b95a5;--line:#262d38;--accent:#6ea8ff}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:820px;margin:0 auto;padding:28px 16px 64px}
header h1{margin:0 0 4px;font-size:1.7rem}
header p{margin:0 0 22px;color:var(--muted);font-size:.95rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 22px;margin:0 0 18px}
.card.top{border-left:4px solid var(--accent)}
.card>h2{margin:0 0 10px;font-size:1.15rem}
h3,h4{margin:18px 0 6px;font-size:1.02rem}
h3:first-child,h4:first-child{margin-top:0}
p{margin:8px 0}
ul{margin:6px 0 6px 0;padding-left:22px}
li{margin:3px 0}
strong{font-weight:650}
code{background:var(--bg);border:1px solid var(--line);border-radius:5px;padding:0 5px;font-size:.9em}
hr{border:0;border-top:1px solid var(--line);margin:16px 0}
.note{color:var(--muted);font-size:.85rem;margin-top:26px}
details.card>summary{cursor:pointer;font-weight:650;font-size:1.05rem}
details.card[open]>summary{margin-bottom:10px}
"""


def _fix_text(t):
    """Clean up math-style artifacts some AI answers contain."""
    t = t.replace("$\\ge$", "≥").replace("$\\le$", "≤").replace("\\ge", "≥").replace("\\le", "≤")
    t = t.replace("\\$", "$")
    return t


def _inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)([^*]+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    return s


def md_to_html(md):
    """Small markdown subset: headings, bullets (nested), bold, italic, code, rules, paragraphs."""
    out, stack, para = [], [], []

    def flush_para():
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
            para.clear()

    def close_lists(to=0):
        while len(stack) > to:
            stack.pop()
            out.append("</ul>")

    for raw in _fix_text(md).splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush_para()
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush_para(); close_lists()
            level = min(max(len(m.group(1)) + 1, 3), 4)  # page title is h1, cards use h2
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            continue
        if re.match(r"^\s*(-{3,}|\*{3,})\s*$", line):
            flush_para(); close_lists()
            out.append("<hr>")
            continue
        m = re.match(r"^(\s*)([*\-•]|\d+[.)])\s+(.*)$", line)
        if m:
            flush_para()
            depth = len(m.group(1).replace("\t", "    ")) // 2
            while len(stack) < depth + 1:
                stack.append(1)
                out.append("<ul>")
            close_lists(depth + 1)
            out.append(f"<li>{_inline(m.group(3))}</li>")
            continue
        close_lists()
        para.append(line.strip())
    flush_para()
    close_lists()
    return "\n".join(out)


def build_html(title, subtitle, top_md, details):
    """top_md = the merged brief. details = [(heading, md), ...] shown collapsed."""
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body><main>",
        f"<header><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></header>",
        f"<section class='card top'>{md_to_html(top_md)}</section>",
    ]
    for heading, md in details:
        parts.append(f"<details class='card'><summary>{html.escape(heading)}</summary>"
                     f"{md_to_html(md)}</details>")
    parts.append("<p class='note'>Research summary from public market data and news. "
                 "Not financial advice.</p></main></body></html>")
    return "".join(parts)


def save_and_open(page_html, stamp_name):
    os.makedirs("reports", exist_ok=True)
    path = Path("reports") / f"{stamp_name}.html"
    path.write_text(page_html, encoding="utf-8")
    latest = Path("reports") / "latest.html"   # bookmark this one
    latest.write_text(page_html, encoding="utf-8")
    opened = False
    if os.getenv("AUTO_OPEN", "1") != "0" and not os.getenv("CI"):
        try:
            opened = webbrowser.open(latest.resolve().as_uri())
        except Exception:  # noqa: BLE001
            opened = False
    return str(path), opened
