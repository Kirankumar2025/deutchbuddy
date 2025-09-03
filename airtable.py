import os, requests, datetime

AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE_WORDS = os.getenv("AIRTABLE_TABLE_WORDS", "Words")
TABLE_GRAMMAR = os.getenv("AIRTABLE_TABLE_GRAMMAR", "GrammarNotes")

API = "https://api.airtable.com/v0"

def _headers():
    return {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type":"application/json"}

def create_word(record: dict):
    url = f"{API}/{BASE_ID}/{TABLE_WORDS}"
    data = {"records":[{"fields": record}]}
    r = requests.post(url, headers=_headers(), json=data, timeout=30)
    r.raise_for_status()
    return r.json()

def list_due_words(limit=20):
    now_iso = datetime.datetime.utcnow().isoformat()+"Z"
    formula = f"OR({{due_at}} <= '{now_iso}', {{due_at}} = BLANK())"
    url = f"{API}/{BASE_ID}/{TABLE_WORDS}?filterByFormula={requests.utils.quote(formula)}&maxRecords={limit}&sort[0][field]=due_at&sort[0][direction]=asc"
    r = requests.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json().get("records", [])

def update_word(record_id: str, fields: dict):
    url = f"{API}/{BASE_ID}/{TABLE_WORDS}"
    data = {"records":[{"id": record_id, "fields": fields}]}
    r = requests.patch(url, headers=_headers(), json=data, timeout=30)
    r.raise_for_status()
    return r.json()

def create_grammar(note: dict):
    url = f"{API}/{BASE_ID}/{TABLE_GRAMMAR}"
    data = {"records":[{"fields": note}]}
    r = requests.post(url, headers=_headers(), json=data, timeout=30)
    r.raise_for_status()
    return r.json()

def count_words():
    url = f"{API}/{BASE_ID}/{TABLE_WORDS}?pageSize=100"
    r = requests.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    return len(r.json().get("records", []))
