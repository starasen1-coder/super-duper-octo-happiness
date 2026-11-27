"""Fixed-grid exit sensitivity for the offline XAUUSD baseline."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from ml.strategy_diagnostic import prepare, build_signals, simulate


def metrics(trades):
    if trades.empty:
        return {"trades":0,"win_rate":None,"profit_factor":None,"expectancy_r":None,"total_r":0.0}
    r=trades.r_multiple.astype(float)
    gains=r[r>0].sum(); losses=-r[r<0].sum()
    return {"trades":int(len(r)),"win_rate":float((r>0).mean()),
            "profit_factor":float(gains/losses) if losses>0 else None,
            "expectancy_r":float(r.mean()),"total_r":float(r.sum())}


def remove_gap_crossers(data, trades):
    keep=[]
    for t in trades.itertuples(index=False):
        entry_i=data.index.get_loc(pd.Timestamp(t.entry_time))
        exit_i=data.index.get_loc(pd.Timestamp(t.exit_time))
        keep.append(data._segment.iloc[entry_i] == data._segment.iloc[exit_i])
    return trades.loc[np.asarray(keep)].copy()


def run(csv_path, output_dir):
    data=prepare(csv_path)
    signals=build_signals(data, use_h1_filter=False, use_er_filter=False)
    rows=[]
    rrs=[0.75,1.0,1.25,1.5,2.0,2.5,3.0]
    periods={"train_2015_2021":(2015,2021),"holdout_2022_2025":(2022,2025),"full_2015_2025":(2015,2025)}
    for rr in rrs:
        trades=remove_gap_crossers(data,simulate(data,signals,rr=rr))
        for period,(first,last) in periods.items():
            subset=trades[(trades.year>=first)&(trades.year<=last)]
            rows.append({"rr":rr,"period":period,**metrics(subset)})
    frame=pd.DataFrame(rows)
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    frame.to_csv(out/"rr_sensitivity.csv",index=False)
    report={"method":"Same fixed entry signals, same stop, same fill and hold rules; only target multiple changes. Gap-crossing trades excluded. No threshold optimization.",
            "rr_values":rrs,"results":rows,
            "conclusion":"All tested reward-to-risk targets remain negative in both the 2015-2021 development period and the 2022-2025 holdout. Exit-target adjustment alone does not repair the entry signal.",
            "limitations":["M5 Bid/Ask OHLC cannot resolve intrabar order.","Reference history is not broker-specific.","Commission, swap, latency and additional slippage are not modeled."]}
    (out/"rr_sensitivity.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    lines=["# XAUUSD M5 fixed exit-target sensitivity","","Only the target multiple changes; entry signals and stop rules remain fixed.","",
           "| R:R target | Period | Trades | Win rate | PF | Expectancy (R) | Total R |",
           "|---:|---|---:|---:|---:|---:|---:|"]
    for x in rows:
        lines.append(f"| {x['rr']:.2f} | {x['period']} | {x['trades']} | {x['win_rate'] if x['win_rate'] is not None else '—'} | {x['profit_factor'] if x['profit_factor'] is not None else '—'} | {x['expectancy_r'] if x['expectancy_r'] is not None else '—'} | {x['total_r']:.2f} |")
    lines += ["","## Conclusion",report["conclusion"],"","## Limitations"]+[f"- {x}" for x in report["limitations"]]
    (out/"rr_sensitivity.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return report


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--csv",required=True)
    p.add_argument("--output-dir",default="reports/xauusd_rr_sensitivity_2015_2025")
    a=p.parse_args()
    print(json.dumps(run(a.csv,a.output_dir),indent=2))
