# super-duper-octo-happiness

MT5 EA project with a local LLM proxy and offline market-data research tools.

## Environment

- Python 3.11 (see `.python-version`)
- Node.js 22 LTS and npm (see `.nvmrc`)
- Create a virtual environment: `python -m venv .venv`
- Install data dependencies: `python -m pip install -r requirements-data.txt`
- Install ML dependencies only when needed: `python -m pip install -r requirements-ml.txt`

## XAUUSD historical data

The branch includes a downloader for the public EV Trading Labs XAUUSD M5
2025 Bid/Ask archive and a separate Dukascopy multi-year downloader.

```powershell
npm run data:ev -- --year 2025 --output data\XAUUSD_M5_BID_ASK_2025.csv
npm run data:validate -- --csv data\XAUUSD_M5_BID_ASK_2025.csv --json data\XAUUSD_M5_quality_2025.json
npm run test:python
```

The source catalogue lists 70,906 bars for the 2025 archive; this is not a
validation result. The validator reports duplicates, invalid OHLC, spread
consistency and timestamp gaps. Weekly/session closures are distinguished
from short intraday gaps. Raw CSV files remain local and are excluded from Git.

Attribution: EV Trading Labs, https://evtradelabs.com/data.
The data is Dukascopy-derived, not an AMarkets broker feed, and does not
establish strategy profitability or broker-specific execution costs.

## Project components

- `LLM_Advisor.mq5` — MT5 EA framework.
- `proxy_server.py` — local LLM proxy.
- `ml/edge_model.py` — PyTorch sequence classifier.
- `ml/walk_forward.py` — chronological walk-forward validation.
- `ml/research.py` — initial sweep/impulse benchmark, not a full EA reproduction.
- `ml/download_evtradelabs.py` — public 2025 Bid/Ask archive to canonical CSV.
- `ml/validate_market_data.py` — quote integrity, spread and gap diagnostics.
