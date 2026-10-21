"""Локальный прокси: MT5-советник -> этот сервер -> модель Claude -> JSON-решение.

Запуск:  uvicorn proxy_server:app --host 127.0.0.1 --port 8000
Ключ API берётся из .env (ANTHROPIC_API_KEY), в советнике его нет.
"""
import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

load_dotenv()

MODEL = os.getenv("MODEL", "claude-sonnet-4-6")
client = Anthropic(timeout=15.0, max_retries=0)
app = FastAPI()

SYSTEM = (
    "Ты помощник-фильтр для торгового советника по XAUUSD. "
    "Тебе приходит JSON: сигнал советника (signal), цена, Volume Profile "
    "(poc, vah, val), сессия и последние свечи [open, high, low, close, tick_volume]. "
    "Оцени, стоит ли подтвердить сигнал. Отвечай ТОЛЬКО JSON без пояснений вокруг: "
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
    data = json.loads(text[start : end + 1])
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
        msg = client.messages.create(
            model=MODEL,
            max_tokens=300,
            system=SYSTEM,
            messages=[{"role": "user", "content": s.model_dump_json()}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        result = _parse(text)
    except Exception as e:  # сеть, лимиты, невалидный JSON
        result = _fallback(f"error: {type(e).__name__}")
    print(s.symbol, s.timeframe, s.signal, "->", result, flush=True)  # лог решений
    return result


@app.get("/health")
def health() -> dict:
    return {"ok": True, "model": MODEL}
