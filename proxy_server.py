"""Local bridge: MT5 EA -> OpenAI-compatible LLM endpoint -> JSON decision.

The endpoint is configured through OPENAI_BASE_URL and OPENAI_API_KEY.
For research, keep LLM filtering optional; deterministic EA rules remain the gate.
"""
import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

BASE_URL = os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:3001/v1")
API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL = os.getenv("MODEL", "auto")

client = OpenAI(base_url=BASE_URL, api_key=API_KEY or "local", timeout=15.0, max_retries=0)
app = FastAPI()

SYSTEM = (
    "Ты помощник-фильтр для торгового советника по XAUUSD. "
    "Тебе приходит JSON: сигнал детерминированного советника, цена, Volume Profile "
    "(poc, vah, val), сессия и последние свечи [open, high, low, close, tick_volume]. "
    "Нельзя создавать новый сигнал или отменять обязательные структурные правила. "
    "Оцени только подтверждение уже сформированного setup. "
    "Отвечай ТОЛЬКО JSON: "
    '{"bias":"long|short|none","confidence":0.0-1.0,"reason":"коротко"}'
)


class Snapshot(BaseModel):
    symbol: str
    timeframe: str
    session: str = ""
    signal: str = "none"
    price: float
    poc: float | None = None
    vah: float | None = None
    val: float | None = None
    candles: list[list[float]] = []


def _fallback(reason: str) -> dict:
    return {"bias": "none", "confidence": 0.0, "reason": reason}


def _parse(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        return _fallback("no json")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return _fallback("invalid json")
    bias = str(data.get("bias", "none")).lower()
    if bias not in ("long", "short", "none"):
        bias = "none"
    try:
        conf = max(0.0, min(1.0, float(data.get("confidence", 0))))
    except (TypeError, ValueError):
        conf = 0.0
    return {"bias": bias, "confidence": conf, "reason": str(data.get("reason", ""))[:200]}


@app.post("/decide")
def decide(s: Snapshot) -> dict:
    try:
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            max_tokens=300,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": s.model_dump_json()},
            ],
        )
        text = response.choices[0].message.content or ""
        result = _parse(text)
    except Exception as e:
        result = _fallback(f"error: {type(e).__name__}")
    print(s.symbol, s.timeframe, s.signal, "->", result, flush=True)
    return result


@app.get("/health")
def health() -> dict:
    return {"ok": True, "model": MODEL, "base_url": BASE_URL}
