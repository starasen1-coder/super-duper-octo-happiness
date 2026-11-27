"""CLI for normalized CSV data; strategy logic stays separate from execution model."""
from __future__ import annotations
import argparse
import pandas as pd
from .data_loader import normalize_ohlcv, normalize_spread, merge_spread

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ohlcv", required=True)
    p.add_argument("--spread", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    price = normalize_ohlcv(pd.read_csv(args.ohlcv))
    spread = normalize_spread(pd.read_csv(args.spread))
    merge_spread(price, spread).to_csv(args.output, index=False)
    print(f"wrote {args.output}")

if __name__ == "__main__":
    main()
