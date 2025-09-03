import os, json, requests, re
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv
from datetime import datetime
from pydantic import BaseModel
from srs import sm2_next, next_due_date
from airtable import create_word, list_due_words, update_word, create_grammar, count_words
from prompts import SYSTEM_PROMPT

# Load env vars
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "hook")
APP_BASE_URL = os.getenv("APP_BASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

app = FastAPI(title="DeutschBuddy")

class TelegramUpdate(BaseModel):
    update_id: int | None = None
    message: dict | None = None
    callback_query: dict | None = None

def tg_send(chat_id: int, text: str, reply_markup: dict|None=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    r = requests.post(f"{TG_API}/sendMessage", data=data, timeout=30)
    return r.json()

def openai_json(prompt: str):
    """Call OpenAI Chat Completions; attempt to parse JSON from response."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type":"application/json"}
    messages = [
        {"role":"system","content": SYSTEM_PROMPT},
        {"role":"user","content": prompt}
    ]
    body = {"model":"gpt-4o-mini", "messages": messages, "temperature": 0.2}
    r = requests.post(url, headers=headers, json=body, timeout=60)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    m = re.search(r'\{[\s\S]*\}', content)  # find first JSON block
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {"text": content}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/set-webhook")
def set_webhook():
    if not APP_BASE_URL:
        raise HTTPException(400, "APP_BASE_URL not set")
    url = f"{TG_API}/setWebhook"
    webhook_url = f"{APP_BASE_URL}/telegram/webhook/{WEBHOOK_SECRET}"
    r = requests.get(url, params={"url": webhook_url}, timeout=30)
    return r.json()

@app.post("/telegram/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request):
    if secret != WEBHOOK_SECRET:
        raise HTTPException(403, "Bad secret")
    payload = await request.json()
    update = TelegramUpdate(**payload)
    if update.message:
        await handle_message(update.message)
    elif update.callback_query:
        await handle_callback(update.callback_query)
    return {"ok": True}

async def handle_message(msg: dict):
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()

    if text.startswith("/start"):
        tg_send(chat_id,
            "👋 Hallo! Ich bin <b>DeutschBuddy</b>.\n\n"
            "Befehle:\n"
            "• /add der Tisch | table | die Tische | Möbel\n"
            "• /explain Dativartikel\n"
            "• /quiz 5\n"
            "• /due\n"
            "• /stats")
        return

    if text.startswith("/add"):
        # /add der Tisch | table | die Tische | Möbel
        payload = text[4:].strip().lstrip()
        parts = [p.strip() for p in payload.split("|")]
        while len(parts) < 4:
            parts.append("")
        word, translation, plural, topic = parts[:4]
        prompt = f"ADD WORD -> {word} | {translation} | {plural} | {topic}. Return JSON per spec."
        data = openai_json(prompt)
        if "lemma" in data:
            record = {
                "lemma": data.get("lemma") or word,
                "article": data.get("article"),
                "gender": data.get("gender"),
                "plural": data.get("plural") or plural or "-",
                "part_of_speech": data.get("pos") or "",
                "translation": data.get("translation") or translation,
                "example_de": data.get("example_de",""),
                "example_en": data.get("example_en",""),
                "topic": data.get("topic") or topic,
                "cefr": data.get("cefr","A1"),
                "ease": 2.5,
                "interval": 0,
                "repetitions": 0,
                "due_at": datetime.utcnow().isoformat()+"Z",
                "created_at": datetime.utcnow().isoformat()+"Z"
            }
            try:
                create_word(record)
                tg_send(chat_id,
                    f"✅ Hinzugefügt: <b>{(record['article'] or '').strip()} {record['lemma']}</b> — {record['translation']}\n"
                    f"<i>{record['example_de']}</i>\n{record['example_en']}")
            except Exception as e:
                tg_send(chat_id, f"⚠️ Konnte nicht speichern: {e}")
        else:
            tg_send(chat_id, f"⚠️ Verstanden, aber kein JSON erhalten: {data}")
        return

    if text.startswith("/explain"):
        topic = text[8:].strip() or "Artikel und Kasus"
        data = openai_json(f"EXPLAIN -> {topic}. Return JSON per spec.")
        if "summary" in data:
            try:
                create_grammar({
                    "topic": data.get("topic", topic),
                    "note": data.get("summary",""),
                    "examples_de": "\n".join([ex.get("de","") for ex in data.get("examples", [])]),
                    "examples_en": "\n".join([ex.get("en","") for ex in data.get("examples", [])]),
                    "level": "A1-A2",
                    "tags": "explain",
                    "created_at": datetime.utcnow().isoformat()+"Z"
                })
            except Exception:
                pass
            lines = [f"📘 <b>{data.get('topic', topic)}</b>", data.get("summary","")]
            if data.get("rule_table"):
                headers = " | ".join(data["rule_table"][0])
                rows = [" | ".join(r) for r in data["rule_table"][1:]]
                lines += ["", f"<b>Regeln:</b>\n{headers}", *rows]
            if data.get("examples"):
                lines.append("\n<b>Beispiele:</b>")
                for ex in data["examples"]:
                    lines.append(f"• <i>{ex.get('de','')}</i> — {ex.get('en','')}")
            if data.get("quick_check"):
                lines.append("\n<b>Quick-Check:</b>")
                for qc in data["quick_check"]:
                    lines.append(f"Q: {qc.get('q','')}\nA: {qc.get('a','')}")
            tg_send(chat_id, "\n".join(lines))
        else:
            tg_send(chat_id, f"⚠️ Konnte das Thema nicht erklären. Antwort: {data}")
        return

    if text.startswith("/quiz"):
        try:
            n = int(text.split(" ",1)[1])
        except Exception:
            n = 5
        try:
            records = list_due_words(limit=n)
        except Exception as e:
            tg_send(chat_id, f"⚠️ Konnte fällige Karten nicht laden: {e}")
            return
        if not records:
            tg_send(chat_id, "🎉 Keine fälligen Karten. /add um neue Wörter zu lernen!")
            return
        for rec in records:
            f = rec["fields"]
            lemma = f.get("lemma")
            article = f.get("article") or ""
            translation = f.get("translation")
            prompt = f"QUIZ one MCQ about '{article} {lemma}' meaning '{translation}'. Include 4 choices with 1 correct. Return JSON per spec."
            q = openai_json(prompt)
            if "prompt" in q and "choices" in q:
                kb = {"inline_keyboard":[[{"text": c, "callback_data": json.dumps({"rid": rec['id'], "a": c, "correct": q.get('answer')})}] for c in q["choices"]]}
                tg_send(chat_id, f"📝 {q.get('prompt')}", reply_markup=kb)
            else:
                tg_send(chat_id, f"• {article} <b>{lemma}</b> → {translation}\nAntwort: {f.get('example_de','')}")
        return

    if text.startswith("/due"):
        try:
            due = list_due_words(limit=100)
            tg_send(chat_id, f"📅 Fällig heute: <b>{len(due)}</b>")
        except Exception as e:
            tg_send(chat_id, f"⚠️ Fehler: {e}")
        return

    if text.startswith("/stats"):
        try:
            total = count_words()
            tg_send(chat_id, f"📊 Wörter in deiner Sammlung: <b>{total}</b>")
        except Exception as e:
            tg_send(chat_id, f"⚠️ Fehler: {e}")
        return

    # Fallback → treat free text as an /explain request
    data = openai_json(f"EXPLAIN -> {text}. Return JSON per spec.")
    if "summary" in data:
        tg_send(chat_id, data.get("summary","(keine Zusammenfassung)"))
    else:
        tg_send(chat_id, "Ich habe dich nicht verstanden. Versuche /add, /explain, /quiz, /due, /stats.")

async def handle_callback(cb: dict):
    chat_id = cb["message"]["chat"]["id"]
    data = json.loads(cb["data"])
    rid = data["rid"]
    chosen = data["a"]
    correct = data["correct"]
    quality = 2 if chosen == correct else 0  # Good vs Again

    try:
        e,i,r = 2.5, 0, 0
        e,i,r = sm2_next(e,i,r,quality)
        update_word(rid, {"ease": e, "interval": i, "repetitions": r, "due_at": next_due_date(i)})
    except Exception:
        pass

    if chosen == correct:
        tg_send(chat_id, "✅ Richtig!")
    else:
        tg_send(chat_id, f"❌ Falsch. Richtige Antwort: <b>{correct}</b>")
