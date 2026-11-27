"""Descriptive loss diagnostics for the offline XAUUSD M5 research run."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from ml.strategy_diagnostic import prepare, build_signals, simulate, detect_sweeps, classify_impulse


def _pf(r):
    gains = r[r > 0].sum()
    losses = -r[r < 0].sum()
    return float(gains / losses) if losses > 0 else None


def _stats(g):
    r = g.r_multiple.astype(float)
    return {"trades": int(len(g)), "win_rate": float((r > 0).mean()),
            "profit_factor": _pf(r), "expectancy_r": float(r.mean()), "total_r": float(r.sum())}


def _buckets(frame, column, bins, min_n=20):
    x = frame.copy()
    x["bucket"] = pd.cut(x[column], bins=bins, include_lowest=True)
    result = []
    for label, group in x.groupby("bucket", observed=True):
        if len(group) >= min_n:
            result.append({"bucket": str(label), **_stats(group)})
    return result


def analyze(csv_path, output_dir):
    d = prepare(csv_path)
    signals = build_signals(d, use_h1_filter=False, use_er_filter=False)
    trades = simulate(d, signals)
    signal_map = signals.set_index("signal_i", drop=False)
    sweep = detect_sweeps(d.rename(columns={"mid_high":"high","mid_low":"low","mid_close":"close"}), 36)
    classify_impulse(d.rename(columns={"mid_open":"open","mid_high":"high","mid_low":"low","mid_close":"close"}), 1.4, .65)
    rows = []
    for t in trades.itertuples(index=False):
        si = d.index.get_loc(pd.Timestamp(t.signal_time))
        fi = d.index.get_loc(pd.Timestamp(t.entry_time))
        xi = d.index.get_loc(pd.Timestamp(t.exit_time))
        s = signal_map.loc[si]
        direction, entry, stop = int(s.direction), float(s.entry), float(s.stop)
        risk, atr = abs(entry-float(stop)), float(s.atr)
        sw_i, ob_i = int(s.sweep_i), int(s.ob_i)
        level = float(sweep.sweep_level_long.iloc[sw_i] if direction == 1 else sweep.sweep_level_short.iloc[sw_i])
        extreme = float(d.mid_low.iloc[sw_i] if direction == 1 else d.mid_high.iloc[sw_i])
        depth = abs(level-extreme)
        span = float(d.mid_high.iloc[si]-d.mid_low.iloc[si])
        body = abs(float(d.mid_close.iloc[si]-d.mid_open.iloc[si]))
        same_segment = d._segment.iloc[fi] == d._segment.iloc[xi]
        # Exclude exit candle from MFE/MAE: OHLC does not reveal intrabar order.
        if xi > fi and direction == 1:
            mfe = (float(d.bid_high.iloc[fi:xi].max())-entry)/risk
            mae = (entry-float(d.bid_low.iloc[fi:xi].min()))/risk
        elif xi > fi:
            mfe = (entry-float(d.ask_low.iloc[fi:xi].min()))/risk
            mae = (float(d.ask_high.iloc[fi:xi].max())-entry)/risk
        else:
            mfe = mae = 0.0
        if direction == 1:
            dual = bool(d.bid_low.iloc[xi] <= stop and d.bid_high.iloc[xi] >= entry+2*risk)
        else:
            dual = bool(d.ask_high.iloc[xi] >= stop and d.ask_low.iloc[xi] <= entry-2*risk)
        spread = float(t.spread_entry)
        rows.append({
            "year":int(t.year), "signal_time":t.signal_time, "entry_time":t.entry_time,
            "exit_time":t.exit_time, "direction":"long" if direction==1 else "short",
            "result":t.result, "r_multiple":float(t.r_multiple),
            "gap_class":"continuous" if same_segment else "crossed_data_gap",
            "ambiguous_stop_target_same_bar":dual,
            "entry_hour_utc":pd.Timestamp(t.entry_time).hour,
            "h1_efficiency_ratio":float(s.h1_er) if pd.notna(s.h1_er) else np.nan,
            "stop_distance_atr":risk/atr if atr else np.nan,
            "impulse_range_atr":span/atr if atr else np.nan,
            "impulse_body_fraction":body/span if span else np.nan,
            "sweep_depth_atr":depth/atr if atr else np.nan,
            "bars_signal_to_fill":fi-si, "spread_to_risk":spread/risk if risk else np.nan,
            "mfe_before_exit_bar_r":mfe, "mae_before_exit_bar_r":mae,
            "duration_bars":xi-fi
        })
    f = pd.DataFrame(rows)
    valid = f[f.gap_class=="continuous"].copy()
    losses = valid[valid.r_multiple<0]
    stop_losses = losses[losses.result=="SL"]
    ambiguous = stop_losses[stop_losses.ambiguous_stop_target_same_bar]
    # An extreme upper bound, not a plausible estimate: every ambiguous candle is assumed to hit TP first.
    optimistic = valid.r_multiple.copy()
    optimistic.loc[ambiguous.index] = 2.0
    report = {
        "simulated_trades":int(len(f)), "continuous_trades":int(len(valid)),
        "gap_crossing_trades_excluded":int((f.gap_class!="continuous").sum()),
        "baseline_continuous":_stats(valid),
        "outcomes":{str(k):int(v) for k,v in valid.result.value_counts().items()},
        "loss_classification":{
            "clear_stop_without_same_bar_target":int((~stop_losses.ambiguous_stop_target_same_bar).sum()),
            "ambiguous_stop_and_target_same_bar":int(len(ambiguous)),
            "stop_after_at_least_1R_favorable_excursion_before_exit_bar":int((stop_losses.mfe_before_exit_bar_r>=1).sum()),
            "stop_without_0_5R_favorable_excursion_before_exit_bar":int((stop_losses.mfe_before_exit_bar_r<.5).sum()),
            "negative_time_exits":int((losses.result=="TIME").sum())
        },
        "all_ambiguous_as_target_upper_bound":_stats(pd.DataFrame({"r_multiple":optimistic})),
        "yearly":{str(int(y)):_stats(g) for y,g in valid.groupby("year")},
        "buckets":{
            "h1_efficiency_ratio":_buckets(valid.dropna(subset=["h1_efficiency_ratio"]),"h1_efficiency_ratio",[-.001,.1,.2,.3,.4,.5,.6,1.001]),
            "stop_distance_atr":_buckets(valid,"stop_distance_atr",[0,.25,.5,.75,1,1.5,2,10]),
            "sweep_depth_atr":_buckets(valid,"sweep_depth_atr",[0,.05,.1,.2,.3,.5,1,10]),
            "impulse_range_atr":_buckets(valid,"impulse_range_atr",[0,1.4,1.6,2,2.5,3,10]),
            "spread_to_risk":_buckets(valid,"spread_to_risk",[0,.1,.15,.2,.3,.5,1,10]),
            "bars_signal_to_fill":_buckets(valid,"bars_signal_to_fill",[0,1,2,3,4,6,9,13])
        },
        "limitations":[
            "Descriptive groups are not causal explanations or validated filters.",
            "MFE/MAE exclude the exit candle because OHLC cannot reveal intrabar ordering.",
            "Gap-crossing trades are excluded from continuous-trade statistics.",
            "The all-ambiguous-as-target result is an unrealistic upper bound, not an alternative backtest.",
            "Reference quotes are not broker-specific; commissions, swaps and additional slippage are not modeled."
        ]
    }
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    f.to_csv(out/"trade_outcome_diagnostics.csv",index=False)
    (out/"loss_reason_analysis.json").write_text(json.dumps(report,indent=2,default=str),encoding="utf-8")
    lines=["# XAUUSD M5 loss analysis","","Descriptive analysis only; no parameter optimization.","",
           f"- Simulated trades: {len(f)}",f"- Continuous trades: {len(valid)}",
           f"- Gap-crossing trades excluded: {report['gap_crossing_trades_excluded']}",
           f"- Baseline PF: {report['baseline_continuous']['profit_factor']:.3f}",
           f"- Baseline expectancy: {report['baseline_continuous']['expectancy_r']:.3f}R","",
           "## Loss classification","","| Category | Count |","|---|---:|"]
    for k,v in report["loss_classification"].items(): lines.append(f"| {k} | {v} |")
    lines += ["","## Optimistic ambiguity bound","",
              "Assuming every stop/target double-touch candle reached target first still does not establish positive expectancy.",
              f"- PF: {report['all_ambiguous_as_target_upper_bound']['profit_factor']:.3f}",
              f"- Expectancy: {report['all_ambiguous_as_target_upper_bound']['expectancy_r']:.3f}R",
              f"- Total: {report['all_ambiguous_as_target_upper_bound']['total_r']:.2f}R"]
    for title,key in [("H1 efficiency ratio","h1_efficiency_ratio"),("Stop distance / ATR","stop_distance_atr"),
                      ("Sweep depth / ATR","sweep_depth_atr"),("Impulse range / ATR","impulse_range_atr"),
                      ("Spread / risk","spread_to_risk"),("Bars from signal to fill","bars_signal_to_fill")]:
        lines += ["",f"## {title}","","| Bucket | Trades | Win rate | PF | Expectancy (R) |","|---|---:|---:|---:|---:|"]
        for x in report["buckets"][key]:
            lines.append(f"| {x['bucket']} | {x['trades']} | {x['win_rate']:.3f} | {x['profit_factor'] if x['profit_factor'] is not None else '—'} | {x['expectancy_r']:.3f} |")
    lines += ["","## Limitations"]+[f"- {x}" for x in report["limitations"]]
    (out/"loss_reason_analysis.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return report


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--csv",required=True)
    p.add_argument("--output-dir",default="reports/xauusd_loss_analysis_2015_2025")
    a=p.parse_args()
    print(json.dumps(analyze(a.csv,a.output_dir),indent=2,default=str))
