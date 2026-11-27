# FreeLLMAPI / OB-1 integration

OB-1's current documentation states that the old self-hosted FreeLLMAPI proxy path has been replaced by an embedded free-models router in the OB-1 CLI. There is no separate FreeLLMAPI repository/server required for the OB-1 path.

This repository still exposes a small local HTTP bridge for MT5. The bridge should call an OpenAI-compatible endpoint, including a local FreeLLMAPI-compatible gateway when one is available.

## Local configuration

Set these values in `.env`:

```text
OPENAI_BASE_URL=http://127.0.0.1:3001/v1
OPENAI_API_KEY=your_local_or_provider_key
MODEL=auto
```

Do not commit `.env`.

## MT5

The EA calls:

```text
POST http://127.0.0.1:8000/decide
```

The Python bridge calls the configured OpenAI-compatible endpoint.

## Important separation

The LLM is a confirmation/filtering layer only. It cannot bypass deterministic structure, liquidity sweep, impulse, OB-retest and risk checks implemented by the EA.

## Verification

1. Start the local model router/agent environment.
2. Start the Python bridge.
3. Check `GET /health`.
4. Attach the EA to XAUUSD M5.
5. Verify that NO TRADE reasons are logged.
6. Run MT5 Strategy Tester and archive the report before comparing versions.
