"""OpenChuckTrade Quote API — openD pushes latest quotes here.

The Streamlit app reads data/now_prices.json on every rerun, so a POST to
this API is picked up by the app automatically (auto-refresh ~15s).

Endpoints:
  GET  /            -> info
  GET  /prices      -> current price map (read-only, no key needed)
  POST /quote       -> body {"quotes": {"371": 1.55, "9888": 90.0}} with
                       header "x-api-key: <key>" (partial updates OK)

Run: uvicorn api:app --host 0.0.0.0 --port 8502
"""
import json
import os
import secrets

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

BASE = os.path.dirname(os.path.abspath(__file__))
PRICE_FILE = os.path.join(BASE, "data", "now_prices.json")
KEY_FILE = os.path.join(BASE, "data", "api_key.txt")

app = FastAPI(title="OpenChuckTrade Quote API")


class Quotes(BaseModel):
    quotes: dict


def _load():
    try:
        with open(PRICE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(prices):
    with open(PRICE_FILE, "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)


@app.get("/")
def root():
    return {"ok": True, "endpoints": ["POST /quote", "GET /prices"], "app": "OpenChuckTrade"}


@app.get("/prices")
def get_prices():
    return _load()


@app.post("/quote")
def post_quote(q: Quotes, x_api_key: str = Header(default="")):
    try:
        with open(KEY_FILE, "r", encoding="utf-8") as f:
            expected = f.read().strip()
    except Exception:
        expected = ""
    if not expected or not secrets.compare_digest(x_api_key.strip(), expected):
        raise HTTPException(status_code=401, detail="bad or missing x-api-key")
    cur = _load()
    updated = 0
    for code, price in q.quotes.items():
        try:
            price = float(price)
        except (TypeError, ValueError):
            continue
        if price > 0:
            cur[str(code)] = price
            updated += 1
    _save(cur)
    return {"ok": True, "updated": updated, "total": len(cur)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8502)
