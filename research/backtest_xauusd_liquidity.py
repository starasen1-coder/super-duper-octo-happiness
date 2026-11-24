#!/usr/bin/env python3
import argparse,json,math,urllib.request
from pathlib import Path
import pandas as pd
URL="https://raw.githubusercontent.com/getdata-finance/xauusd-5m-ohlcv-metals-historical-data/main/XAUUSD_5m.csv"

def load(path):
    if not Path(path).exists(): urllib.request.urlretrieve(URL,path)
    return pd.read_csv(path,parse_dates=["datetime"]).sort_values("datetime").drop_duplicates("datetime").reset_index(drop=True)

def run(df,initial=10000,risk_pct=.5,spread=.20):
    prev=df.close.shift(1)
    tr=pd.concat([df.high-df.low,(df.high-prev).abs(),(df.low-prev).abs()],axis=1).max(axis=1)
    df=df.copy(); df["atr"]=tr.rolling(14,min_periods=14).mean(); df["vavg"]=df.volume.shift(1).rolling(20).mean()
    h=df.set_index("datetime").resample("1h").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna().reset_index()
    h["bull"]=(h.close>h.high.shift(2))&(h.low.shift(1)>=h.low.shift(2))&(h.high.shift(1)>=h.high.shift(2))
    h["bear"]=(h.close<h.low.shift(2))&(h.high.shift(1)<=h.high.shift(2))&(h.low.shift(1)<=h.low.shift(2))
    df=pd.merge_asof(df,h[["datetime","bull","bear"]].sort_values("datetime"),on="datetime",direction="backward")
    eq=initial; peak=initial; maxdd=0.; trades=[]; i=40; cooldown=-1
    while i<len(df)-2:
        r=df.iloc[i]
        if i<=cooldown or pd.isna(r.atr) or pd.isna(r.vavg) or not (7<=r.datetime.hour<20): i+=1; continue
        if df.high.iloc[i-24:i].max()-df.low.iloc[i-24:i].min()<r.atr*2.2 or r.volume<r.vavg*1.10: i+=1; continue
        found=None
        for sh in range(2,6):
            s=i-sh
            lo=df.low.iloc[s-36:s].min(); hi=df.high.iloc[s-36:s].max()
            if df.low.iloc[s]<lo and df.close.iloc[s]>lo: found=("buy",lo); break
            if df.high.iloc[s]>hi and df.close.iloc[s]<hi: found=("sell",hi); break
        if not found: i+=1; continue
        side,level=found
        if (side=="buy" and not bool(r.bull)) or (side=="sell" and not bool(r.bear)): i+=1; continue
        rng=r.high-r.low; body=abs(r.close-r.open)
        if rng<=0 or body/rng<.65 or rng<r.atr*1.4: i+=1; continue
        if side=="buy" and not (r.close>r.open and r.close>df.high.iloc[i-3:i].max()): i+=1; continue
        if side=="sell" and not (r.close<r.open and r.close<df.low.iloc[i-3:i].min()): i+=1; continue
        e=i+1; entry=df.open.iloc[e]+(spread/2 if side=="buy" else -spread/2)
        sl=level-r.atr*.20 if side=="buy" else level+r.atr*.20; risk=abs(entry-sl)
        if risk<=0: i+=1; continue
        mn=entry+risk*2 if side=="buy" else entry-risk*2; mx=entry+risk*5 if side=="buy" else entry-risk*5
        liq=df.high.iloc[i-35:i+1].max() if side=="buy" else df.low.iloc[i-35:i+1].min()
        tp=mn if (liq<mn if side=="buy" else liq>mn) else (min(liq,mx) if side=="buy" else max(liq,mx))
        rr=abs(tp-entry)/risk
        if rr<2: i+=1; continue
        j=e; outcome=None
        while j<len(df):
            bh,bl=df.high.iloc[j],df.low.iloc[j]; hit_sl=(bl<=sl) if side=="buy" else (bh>=sl); hit_tp=(bh>=tp) if side=="buy" else (bl<=tp)
            if hit_sl: outcome=-1.; break
            if hit_tp: outcome=rr; break
            j+=1
        if outcome is None: break
        pnl=eq*risk_pct/100*outcome; eq+=pnl; peak=max(peak,eq); maxdd=max(maxdd,(peak-eq)/peak*100)
        trades.append({"entry_time":str(df.datetime.iloc[e]),"exit_time":str(df.datetime.iloc[j]),"side":side,"r":outcome,"pnl":pnl,"equity":eq})
        cooldown=e+8; i=j+1
    t=pd.DataFrame(trades); wins=int((t.r>0).sum()) if len(t) else 0; gp=t.loc[t.pnl>0,"pnl"].sum() if len(t) else 0; gl=-t.loc[t.pnl<0,"pnl"].sum() if len(t) else 0
    return {"start":str(df.datetime.iloc[0]),"end":str(df.datetime.iloc[-1]),"bars":len(df),"initial":initial,"final":eq,"pnl":eq-initial,"return_pct":(eq/initial-1)*100,"max_drawdown_pct":maxdd,"trades":len(t),"wins":wins,"losses":len(t)-wins,"win_rate_pct":wins/len(t)*100 if len(t) else 0,"profit_factor":gp/gl if gl else 0},t

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--data",default="/tmp/XAUUSD_5m.csv"); ap.add_argument("--out",default="results"); a=ap.parse_args()
    Path(a.out).mkdir(parents=True,exist_ok=True); s,t=run(load(a.data))
    Path(a.out,"summary.json").write_text(json.dumps(s,indent=2)); t.to_csv(Path(a.out,"trades.csv"),index=False); t[["exit_time","equity"]].to_csv(Path(a.out,"equity_curve.csv"),index=False) if len(t) else None
    print(json.dumps(s,indent=2))
