#!/usr/bin/env python3
"""Causal event study for XAUUSD M5 liquidity-sweep hypotheses.

Research only. No broker connectivity, order routing, or live trading.
All signals are evaluated after a bar closes; entries use the next bar open.
"""
from __future__ import annotations
import argparse, json, math, urllib.request
from pathlib import Path
import numpy as np
import pandas as pd

URL = "https://raw.githubusercontent.com/getdata-finance/xauusd-5m-ohlcv-metals-historical-data/main/XAUUSD_5m.csv"

def load_data(path: str) -> pd.DataFrame:
    p=Path(path)
    if not p.exists():
        p.parent.mkdir(parents=True,exist_ok=True)
        urllib.request.urlretrieve(URL,p)
    d=pd.read_csv(p)
    d.columns=[c.strip().lower().replace(" ","_") for c in d.columns]
    time_col=next((c for c in ("datetime","timestamp","date_time","time","date") if c in d.columns),None)
    if time_col is None: raise ValueError(f"No timestamp column: {list(d.columns)}")
    d=d.rename(columns={time_col:"time"})
    d["time"]=pd.to_datetime(d.time,utc=True)
    for c in ("open","high","low","close"):
        if c not in d: raise ValueError(f"Missing {c}")
        d[c]=pd.to_numeric(d[c],errors="coerce")
    if "volume" not in d:
        for c in ("tick_volume","vol"):
            if c in d: d=d.rename(columns={c:"volume"}); break
    if "volume" not in d: d["volume"]=np.nan
    d["volume"]=pd.to_numeric(d.volume,errors="coerce")
    d=d.dropna(subset=["time","open","high","low","close"]).sort_values("time").drop_duplicates("time").reset_index(drop=True)
    if not ((d.high>=d[["open","close","low"]].max(axis=1)) & (d.low<=d[["open","close","high"]].min(axis=1))).all():
        raise ValueError("OHLC integrity check failed")
    return d

def add_features(d: pd.DataFrame) -> pd.DataFrame:
    x=d.copy()
    prev=x.close.shift(1)
    tr=pd.concat([x.high-x.low,(x.high-prev).abs(),(x.low-prev).abs()],axis=1).max(axis=1)
    x["atr"]=tr.rolling(14,min_periods=14).mean()
    x["pool_low"]=x.low.shift(1).rolling(36,min_periods=36).min()
    x["pool_high"]=x.high.shift(1).rolling(36,min_periods=36).max()
    x["sweep_long"]=(x.low<x.pool_low)&(x.close>x.pool_low)
    x["sweep_short"]=(x.high>x.pool_high)&(x.close<x.pool_high)
    rng=(x.high-x.low).replace(0,np.nan)
    x["body_frac"]=(x.close-x.open).abs()/rng
    x["imp_long"]=(x.close>x.open)&(x.body_frac>=.65)&(rng>=1.4*x.atr)&(x.close>x.high.shift(1).rolling(3).max())
    x["imp_short"]=(x.close<x.open)&(x.body_frac>=.65)&(rng>=1.4*x.atr)&(x.close<x.low.shift(1).rolling(3).min())
    return x

def outcome(d, entry_i, side, stop, target, horizon=48):
    entry=float(d.open.iloc[entry_i]); risk=abs(entry-stop); end=min(len(d),entry_i+horizon)
    best=0.0; worst=0.0
    for j in range(entry_i,end):
        hi=float(d.high.iloc[j]); lo=float(d.low.iloc[j])
        fav=(hi-entry if side=="long" else entry-lo)/risk
        adv=(entry-lo if side=="long" else hi-entry)/risk
        best=max(best,fav); worst=max(worst,adv)
        sl=(lo<=stop) if side=="long" else (hi>=stop)
        tp=(hi>=target) if side=="long" else (lo<=target)
        if sl and tp: return {"result":"SL_same_bar","exit_i":j,"r":-1.0,"mfe_r":best,"mae_r":worst}
        if sl: return {"result":"SL","exit_i":j,"r":-1.0,"mfe_r":best,"mae_r":worst}
        if tp: return {"result":"TP","exit_i":j,"r":abs(target-entry)/risk,"mfe_r":best,"mae_r":worst}
    j=max(entry_i,end-1); close=float(d.close.iloc[j]); mark=((close-entry) if side=="long" else (entry-close))/risk
    return {"result":"TIMEOUT","exit_i":j,"r":mark,"mfe_r":best,"mae_r":worst}

def select_nonoverlap(t: pd.DataFrame) -> pd.DataFrame:
    if t.empty: return t.copy()
    ordered=t.sort_values("entry_i")
    chosen=[]; free_after=-1
    for _,row in ordered.iterrows():
        if int(row.entry_i)>free_after:
            chosen.append(row); free_after=int(row.exit_i)
    return pd.DataFrame(chosen).reset_index(drop=True)

def evaluate(d, events, label, horizon=48):
    rows=[]
    for e in events:
        i=e["entry_i"]; side=e["side"]; entry=float(d.open.iloc[i]); stop=e["stop"]
        risk=abs(entry-stop)
        if not np.isfinite(risk) or risk<=0: continue
        target=entry+(2*risk if side=="long" else -2*risk)
        z=outcome(d,i,side,stop,target,horizon)
        rows.append({"setup":label,"side":side,"signal_time":str(d.time.iloc[e["signal_i"]]),"entry_time":str(d.time.iloc[i]),"entry_i":i,"exit_time":str(d.time.iloc[z["exit_i"]]),"exit_i":z["exit_i"],"result":z["result"],"r":z["r"],"mfe_r":z["mfe_r"],"mae_r":z["mae_r"],"risk_price":risk})
    t=pd.DataFrame(rows)
    n=len(t); wins=int((t.result=="TP").sum()) if n else 0; losses=int(t.result.str.startswith("SL").sum()) if n else 0
    resolved=wins+losses
    rvals=t.r.dropna() if n else pd.Series(dtype=float)
    nt=select_nonoverlap(t); nr=len(nt); nrvals=nt.r.dropna() if nr else pd.Series(dtype=float)
    cost=[]
    for dollars in (0.0,0.20,0.40,0.80):
        net=(nrvals - dollars/nt.risk_price) if nr else pd.Series(dtype=float)
        cost.append({"round_trip_cost_price":dollars,"nonoverlap_trades":nr,"expectancy_net_R":float(net.mean()) if len(net) else None,"profit_factor_net":float(net[net>0].sum()/-net[net<0].sum()) if len(net) and (net<0).any() else None})
    return {"setup":label,"signals_including_overlaps":n,"wins":wins,"losses":losses,"timeouts":n-resolved,
            "win_rate_resolved_pct":100*wins/resolved if resolved else None,
            "expectancy_R_all_events":float(rvals.mean()) if len(rvals) else None,
            "profit_factor_R_all_events":float(rvals[rvals>0].sum()/-rvals[rvals<0].sum()) if len(rvals) and (rvals<0).any() else None,
            "nonoverlap_trades":nr,"nonoverlap_expectancy_R_gross":float(nrvals.mean()) if len(nrvals) else None,
            "cost_sensitivity_nonoverlap":cost},t

def detect_setups(d):
    base=[]; confirmed=[]; stages={"sweeps":0,"impulse_after_sweep":0,"retest_after_impulse":0,"valid_entries":0}
    # Event-by-event, no future data is used to decide signal; forward bars only determine outcome.
    for s in range(40,len(d)-60):
        r=d.iloc[s]
        if pd.isna(r.atr): continue
        for side,flag in (("long",r.sweep_long),("short",r.sweep_short)):
            if not bool(flag): continue
            stages["sweeps"]+=1
            stop=float(r.low-.15*r.atr) if side=="long" else float(r.high+.15*r.atr)
            base.append({"signal_i":s,"entry_i":s+1,"side":side,"stop":stop})
            # first qualifying displacement within next four completed bars
            imp=None
            for k in range(s+1,min(s+5,len(d)-1)):
                q=d.iloc[k]
                if bool(q.imp_long if side=="long" else q.imp_short):
                    imp=k; break
            if imp is None: continue
            stages["impulse_after_sweep"]+=1
            # Break level is prior 3-bar high/low at impulse time; wait for a retest/hold.
            level=float(d.high.iloc[imp-3:imp].max()) if side=="long" else float(d.low.iloc[imp-3:imp].min())
            ret=None
            for k in range(imp+1,min(imp+7,len(d)-1)):
                q=d.iloc[k]
                if side=="long" and q.low<=level and q.close>level: ret=k; break
                if side=="short" and q.high>=level and q.close<level: ret=k; break
            if ret is None: continue
            stages["retest_after_impulse"]+=1
            # entry after retest close; stop remains beyond sweep extreme.
            confirmed.append({"signal_i":ret,"entry_i":ret+1,"side":side,"stop":stop})
            stages["valid_entries"]+=1
    return stages,base,confirmed

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data",default="/tmp/xauusd_m5.csv"); ap.add_argument("--out",default="results")
    args=ap.parse_args(); out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    raw=load_data(args.data); d=add_features(raw)
    stages,base,confirmed=detect_setups(d)
    s0,t0=evaluate(d,base,"sweep_reclaim_only")
    s1,t1=evaluate(d,confirmed,"sweep_impulse_retest")
    # H1 feature availability audit: each hourly candle becomes usable only after its closing timestamp.
    h=d.set_index("time").resample("1h",label="left",closed="left").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna()
    h["available_at"]=h.index+pd.Timedelta(hours=1)
    summary={"dataset":{"rows":len(d),"start":str(d.time.iloc[0]),"end":str(d.time.iloc[-1]),"timezone":"UTC",
                        "missing_volume":bool(d.volume.isna().all()),"median_bar_minutes":float(d.time.diff().dt.total_seconds().median()/60)},
             "stage_counts":stages,"results":[s0,s1],
             "confirmed_monthly_all_signals":(t1.assign(month=pd.to_datetime(t1.entry_time,utc=True).dt.strftime("%Y-%m")).groupby("month").agg(signals=("r","size"),mean_R=("r","mean")).reset_index().to_dict("records") if len(t1) else []),
             "confirmed_by_side":(t1.groupby("side").agg(trades=("r","size"),mean_R=("r","mean"),wins=("result",lambda x:int((x=="TP").sum())),losses=("result",lambda x:int(x.str.startswith("SL").sum()))).reset_index().to_dict("records") if len(t1) else []),
             "method":{"pool_lookback_bars":36,"sweep":"wick beyond prior rolling extreme and close back across it",
                       "impulse":"within 4 bars; body/range >= 0.65; range >= 1.4 ATR; 3-bar close break",
                       "retest":"within 6 bars; revisit broken level and close back through",
                       "entry":"next bar open after signal close","target":"2R","horizon_bars":48,
                       "same_bar_stop_target":"stop first","spread_commission":"not modeled; OHLCV source is not broker bid/ask",
                       "h1_alignment":"hourly bar available only at its close; not used as a gating filter in this event study"},
             "warning":"Exploratory event study, not a validated strategy. One short sample; no out-of-sample confirmation."}
    (out/"summary.json").write_text(json.dumps(summary,indent=2,allow_nan=False),encoding="utf-8")
    pd.concat([t0,t1],ignore_index=True).to_csv(out/"events.csv",index=False)
    print(json.dumps(summary,indent=2,allow_nan=False))
if __name__=="__main__": main()
