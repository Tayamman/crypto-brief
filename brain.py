"""The 'brain': Google Gemini free tier. Falls back to raw data if no key is set.

Get a free key (no credit card): https://aistudio.google.com/apikey
Put it in .env as GEMINI_API_KEY=...

Model names change over time, so if the default is not available for your key,
this file asks Google which models your key can use and picks a Flash model.
The key is sent in a header and is never printed.
"""
import os
import sys
import time
import requests

BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-flash-latest"
BAD_WORDS = ("preview", "exp", "thinking", "image", "tts", "live", "audio",
             "embedding", "vision", "robotics", "computer", "learnlm")

SYSTEM = (
    "You are a sharp, honest crypto market analyst. Be concise and specific. "
    "Use ONLY the data provided; never invent numbers. State uncertainty plainly. "
    "Do not give financial advice or price predictions; describe what the data shows, "
    "what is notable, and what to watch. Use short bullet points. "
    "Write plain text with simple markdown only (headings, bullets, bold). "
    "Never use LaTeX or math notation: write >= or the word 'above' instead."
)

_model_cache = {"name": None}


def _headers(key):
    return {"x-goog-api-key": key, "Content-Type": "application/json"}


def _discover_model(key):
    r = requests.get(f"{BASE}/models", headers=_headers(key),
                     params={"pageSize": 200}, timeout=30)
    r.raise_for_status()
    names = []
    for m in r.json().get("models", []):
        if "generateContent" in m.get("supportedGenerationMethods", []):
            names.append(m["name"].split("/")[-1])
    if "gemini-flash-latest" in names:
        return "gemini-flash-latest"
    flash = [n for n in names if "flash" in n and not any(b in n for b in BAD_WORDS)]
    flash.sort(key=lambda n: ("lite" in n, n), reverse=False)
    # prefer non-lite, and the highest version string among them
    non_lite = sorted([n for n in flash if "lite" not in n], reverse=True)
    pick = (non_lite or sorted(flash, reverse=True) or names)
    if not pick:
        raise RuntimeError("Your key has no models that support generateContent.")
    return pick[0]


def _generate(key, model, body):
    return requests.post(f"{BASE}/models/{model}:generateContent",
                         headers=_headers(key), json=body, timeout=90)


def ask(task, data_text):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return ("[No GEMINI_API_KEY set, showing raw data only. "
                "Get a free key at https://aistudio.google.com/apikey]\n\n" + data_text)
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user",
                      "parts": [{"text": f"{task}\n\nDATA:\n{data_text}"}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2000},
    }
    model = _model_cache["name"] or os.getenv("GEMINI_MODEL") or DEFAULT_MODEL
    tried_discovery = False
    last = ""
    for attempt in range(5):
        try:
            r = _generate(key, model, body)
            if r.status_code == 200:
                _model_cache["name"] = model
                data = r.json()
                cands = data.get("candidates") or []
                if not cands:
                    return f"[AI returned no answer: {data.get('promptFeedback')}]\n\n{data_text}"
                parts = cands[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts).strip()
                return text or f"[AI returned empty text]\n\n{data_text}"
            last = f"{r.status_code}: {r.text[:250]}"
            if r.status_code in (400, 404) and not tried_discovery:
                tried_discovery = True
                model = _discover_model(key)
                print(f"[brain] switching to model: {model}", file=sys.stderr)
                continue
            if r.status_code in (429, 500, 503):
                time.sleep(15 * (attempt + 1))  # free tier rate limit: wait and retry
                continue
            break
        except Exception as e:  # noqa: BLE001
            last = str(e).replace(key, "***")
            time.sleep(3)
    return f"[AI step failed: {last}]\n\nRaw data:\n{data_text}"
