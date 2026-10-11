"""Shared helpers: HTTP with retries, .env loading, report saving, Telegram."""
import os
import time
import json
import datetime as dt
import requests

# Binance's public market-data mirror. No API key, no account needed.
BINANCE_BASES = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
]


def load_env(path=".env"):
    """Tiny .env loader so you don't need extra libraries."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()


def get_json(url, params=None, retries=3, timeout=20):
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout,
                             headers={"User-Agent": "crypto-agents/1.0"})
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"GET failed: {url} -> {last}")


def get_text(url, retries=3, timeout=20):
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, timeout=timeout,
                             headers={"User-Agent": "Mozilla/5.0 crypto-agents/1.0"})
            r.raise_for_status()
            return r.text
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"GET failed: {url} -> {last}")


def binance(path, params=None):
    """Call a Binance public endpoint, trying each mirror."""
    err = None
    for base in BINANCE_BASES:
        try:
            return get_json(base + path, params, retries=2)
        except Exception as e:  # noqa: BLE001
            err = e
    raise RuntimeError(f"All Binance mirrors failed for {path}: {err}")


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def save_report(name, text):
    os.makedirs("reports", exist_ok=True)
    stamp = now_utc().strftime("%Y-%m-%d_%H%M")
    path = os.path.join("reports", f"{name}_{stamp}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def send_telegram(text):
    """Optional and free. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to enable."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return False
    # Telegram messages max out at 4096 characters.
    for i in range(0, len(text), 4000):
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text[i:i + 4000]},
            timeout=20,
        )
    return True


def _chunks(text, size):
    """Split on line breaks so messages are not cut mid-sentence."""
    out, cur = [], ""
    for line in text.splitlines(keepends=True):
        while len(line) > size:
            if cur:
                out.append(cur)
                cur = ""
            out.append(line[:size])
            line = line[size:]
        if len(cur) + len(line) > size:
            out.append(cur)
            cur = ""
        cur += line
    if cur.strip():
        out.append(cur)
    return out


def send_whatsapp(text):
    """Free WhatsApp message to YOURSELF via CallMeBot (unofficial service).
    Needs WHATSAPP_PHONE (with country code, e.g. +923001234567) and
    WHATSAPP_APIKEY in .env. Setup steps are in README.md.
    """
    phone = os.getenv("WHATSAPP_PHONE", "").strip()
    key = os.getenv("WHATSAPP_APIKEY", "").strip()
    if not phone or not key:
        return False
    ok = True
    for i, part in enumerate(_chunks(text, 1200)):
        if i:
            time.sleep(4)  # be gentle, the service rate-limits
        try:
            r = requests.get("https://api.callmebot.com/whatsapp.php",
                             params={"phone": phone, "text": part, "apikey": key},
                             timeout=40)
            if r.status_code != 200:
                print(f"[whatsapp] failed ({r.status_code}): {r.text[:150]}")
                ok = False
        except Exception as e:  # noqa: BLE001
            print(f"[whatsapp] failed: {str(e).replace(key, '***')}")
            ok = False
    return ok


def send_ntfy(text, title="Crypto Brief"):
    """Free push notification to your phone via ntfy.sh (app: 'ntfy').
    Needs NTFY_TOPIC in .env: a long, random, secret topic name."""
    topic = os.getenv("NTFY_TOPIC", "").strip()
    if not topic:
        return False
    server = os.getenv("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    ok = True
    # 4096-byte limit; a character can be up to 4 bytes, so 1000 chars is always safe.
    for i, part in enumerate(_chunks(text, 1000)):
        try:
            r = requests.post(f"{server}/{topic}", data=part.encode("utf-8"),
                              headers={"Title": f"{title} ({i + 1})" if i else title},
                              timeout=30)
            if r.status_code != 200:
                print(f"[ntfy] failed ({r.status_code}): {r.text[:150]}")
                ok = False
        except Exception as e:  # noqa: BLE001
            print(f"[ntfy] failed: {e}")
            ok = False
    return ok


def send_email(text, subject="Crypto Brief"):
    """Free email to yourself through Gmail. Needs a Google 'App Password'
    (not your normal password): EMAIL_USER and EMAIL_APP_PASSWORD in .env."""
    import smtplib
    from email.message import EmailMessage
    user = os.getenv("EMAIL_USER", "").strip()
    pw = os.getenv("EMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    if not user or not pw:
        return False
    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = os.getenv("EMAIL_TO", "").strip() or user
    msg["Subject"] = subject
    msg.set_content(text)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(user, pw)
            s.send_message(msg)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[email] failed: {str(e).replace(pw, '***')}")
        return False


def notify(text):
    """Send the brief to every channel that is configured."""
    sent = []
    if send_ntfy(text):
        sent.append("ntfy")
    if send_email(text):
        sent.append("Email")
    if send_whatsapp(text):
        sent.append("WhatsApp")
    if send_telegram(text):
        sent.append("Telegram")
    return sent


def money(x):
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1e9:
        return f"{sign}${x / 1e9:.2f}B"
    if x >= 1e6:
        return f"{sign}${x / 1e6:.2f}M"
    if x >= 1e3:
        return f"{sign}${x / 1e3:.1f}K"
    return f"{sign}${x:.0f}"


def dump(obj):
    return json.dumps(obj, indent=1, default=str)
