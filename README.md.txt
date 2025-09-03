# DeutschBuddy (Telegram + Airtable + OpenAI)

## What it does
- Explains German grammar in simple A1–B2 language.
- Stores your vocab with examples.
- Quizzes you using spaced repetition (SM-2).

## Quick start
1) Create Telegram bot (BotFather) → get TELEGRAM_BOT_TOKEN.
2) Create Airtable base with tables `Words` and `GrammarNotes`.
3) Set env vars (see `.env.example`).
4) Deploy (Render/Railway). Start command:
   `uvicorn app:app --host 0.0.0.0 --port 10000`
5) Open `https://<your-app>/set-webhook` once.
6) Chat with your bot: `/start`, `/add`, `/explain`, `/quiz`.

## Airtable tables
**Words**: lemma, article, gender, plural, part_of_speech, translation, example_de, example_en, topic, cefr, ease, interval, repetitions, due_at, created_at  
**GrammarNotes**: topic, note, examples_de, examples_en, level, tags, created_at
