#!/usr/bin/env python3
"""Audit summary/deal-ledger consistency in an MT5 Strategy Tester HTML report.

Standard-library only. It does not rate strategy quality or read graph images.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


class Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.table = self.row = self.cell = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "table":
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(clean("".join(self.cell)))
            self.cell = None
        elif tag == "tr" and self.row is not None and self.table is not None:
            if self.row:
                self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def read_text(path: Path) -> str:
    b = path.read_bytes()
    if b.startswith((b"\xff\xfe", b"\xfe\xff")):
        return b.decode("utf-16")
    if b.startswith(b"\xef\xbb\xbf"):
        return b.decode("utf-8-sig")
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("cp1251")


def number(s: str):
    s = s.replace("\u2212", "-").replace(" ", "").replace("\xa0", "").replace(",", "")
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None


def metric(tables, label):
    for table in tables:
        for row in table:
            for i, cell in enumerate(row):
                if cell.casefold().startswith(label.casefold()):
                    for candidate in row[i + 1:]:
                        v = number(candidate)
                        if v is not None:
                            return v
    return None


def audit(path: Path):
    p = Parser()
    p.feed(read_text(path))
    net = metric(p.tables, "Чистая прибыль:") 
    if net is None:
        net = metric(p.tables, "Net Profit:")
    initial = metric(p.tables, "Начальный депозит:")
    if initial is None:
        initial = metric(p.tables, "Initial Deposit:")

    mode = ""
    deal_table = None
    headers = {"время", "сделка", "символ", "тип", "направление", "прибыль", "баланс"}
    for table in p.tables:
        for row in table:
            for i, cell in enumerate(row):
                if cell.casefold().startswith("валюта:") or cell.casefold().startswith("currency:"):
                    if i + 1 < len(row):
                        mode = row[i + 1]
        for idx, row in enumerate(table):
            if headers.issubset({x.casefold() for x in row}):
                deal_table = (row, table[idx + 1:])
                break
        if deal_table:
            break
    if not deal_table:
        raise ValueError("Cannot find the MT5 Deals/Сделки table.")

    header, rows = deal_table
    ix = {h.casefold(): i for i, h in enumerate(header)}
    def get(row, name):
        i = ix.get(name.casefold())
        return row[i] if i is not None and i < len(row) else ""

    exits = []
    final_balance = None
    for row in rows:
        direction = get(row, "Направление").casefold()
        if not direction:
            continue
        bal = number(get(row, "Баланс"))
        if bal is not None:
            final_balance = bal
        if direction not in {"out", "out by", "out_by", "close", "закрытие"}:
            continue
        pnl = number(get(row, "Прибыль"))
        if pnl is None:
            continue
        commission = number(get(row, "Комиссия")) or 0.0
        swap = number(get(row, "Своп")) or 0.0
        exits.append({
            "time": get(row, "Время"), "pnl": pnl,
            "commission": commission, "swap": swap,
            "reason": get(row, "Комментарий")
        })
    if not exits:
        raise ValueError("No closing deals found.")

    gross_win = sum(x["pnl"] for x in exits if x["pnl"] > 0)
    gross_loss = sum(x["pnl"] for x in exits if x["pnl"] < 0)
    ledger = sum(x["pnl"] for x in exits)
    by_year = defaultdict(lambda: {"trades": 0, "pnl": 0.0, "wins": 0})
    for x in exits:
        year = x["time"][:4] if len(x["time"]) >= 4 else "unknown"
        by_year[year]["trades"] += 1
        by_year[year]["pnl"] += x["pnl"]
        by_year[year]["wins"] += int(x["pnl"] > 0)

    warnings = []
    if net is not None and abs(net - ledger) > 0.02:
        warnings.append(f"Summary net profit {net:.2f} != closing-deal P/L sum {ledger:.2f}.")
    if initial is not None and final_balance is not None and abs(initial + ledger - final_balance) > 0.03:
        warnings.append(f"Initial balance + deal P/L {initial + ledger:.2f} != final ledger balance {final_balance:.2f}.")
    if all(abs(x["commission"]) < 1e-10 for x in exits) and all(abs(x["swap"]) < 1e-10 for x in exits):
        warnings.append("Commission and swap are zero on all exit deals; check tester mode and cost settings.")
    if "пипс" in mode.casefold() or "pip" in mode.casefold():
        warnings.append("Report says profit in pips; MT5 documents this as a rough mode without commissions/swaps and margin control.")
    return {
        "report": str(path),
        "currency_mode": mode,
        "summary_net_profit": net,
        "ledger_pnl_sum": ledger,
        "gross_profit": gross_win,
        "gross_loss": gross_loss,
        "profit_factor_from_ledger": gross_win / abs(gross_loss) if gross_loss else None,
        "closed_deals": len(exits),
        "wins": sum(x["pnl"] > 0 for x in exits),
        "losses": sum(x["pnl"] < 0 for x in exits),
        "average_win": gross_win / sum(x["pnl"] > 0 for x in exits) if any(x["pnl"] > 0 for x in exits) else None,
        "average_loss": gross_loss / sum(x["pnl"] < 0 for x in exits) if any(x["pnl"] < 0 for x in exits) else None,
        "initial_balance": initial,
        "final_ledger_balance": final_balance,
        "commission_sum": sum(x["commission"] for x in exits),
        "swap_sum": sum(x["swap"] for x in exits),
        "by_exit_year": dict(sorted(by_year.items())),
        "warnings": warnings,
        "chart_note": "Embedded PNG charts are not parsed; compare them manually with the summary and deal ledger."
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("report", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        result = audit(args.report)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    for k in ("report", "currency_mode", "summary_net_profit", "ledger_pnl_sum",
              "gross_profit", "gross_loss", "profit_factor_from_ledger",
              "closed_deals", "wins", "losses", "initial_balance", "final_ledger_balance"):
        print(f"{k}: {result[k]}")
    print("By exit year:", json.dumps(result["by_exit_year"], ensure_ascii=False))
    for warning in result["warnings"]:
        print("WARNING:", warning)
    print("NOTE:", result["chart_note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
