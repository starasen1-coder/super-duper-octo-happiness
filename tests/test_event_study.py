import pandas as pd
from research.event_study import add_features, detect_setups, evaluate

def test_features_do_not_use_future_bars():
    d=pd.DataFrame({"time":pd.date_range("2026-01-01",periods=100,freq="5min",tz="UTC"),
                    "open":[100.0]*100,"high":[101.0]*100,"low":[99.0]*100,
                    "close":[100.0]*100,"volume":[1]*100})
    x=add_features(d)
    assert not bool(x.sweep_long.fillna(False).any())
    assert not bool(x.sweep_short.fillna(False).any())

def test_sweep_uses_previous_36_bars_only():
    d=pd.DataFrame({"time":pd.date_range("2026-01-01",periods=60,freq="5min",tz="UTC"),
                    "open":[100.0]*60,"high":[101.0]*60,"low":[99.0]*60,
                    "close":[100.0]*60,"volume":[1]*60})
    d.loc[50,["low","close"]]=[98.0,100.0]
    x=add_features(d)
    assert bool(x.sweep_long.iloc[50])
    assert x.pool_low.iloc[50]==99.0

def test_stop_first_when_both_touched():
    from research.event_study import outcome
    d=pd.DataFrame({"open":[100,100],"high":[103,103],"low":[97,97]})
    z=outcome(d,1,"long",98,102,1)
    assert z["result"]=="SL_same_bar" and z["r"]==-1

def test_nonoverlap_selector_uses_entry_before_prior_exit():
    from research.event_study import select_nonoverlap
    x=pd.DataFrame({"entry_i":[10,15,30],"exit_i":[25,28,40],"r":[1.0,-1.0,2.0]})
    y=select_nonoverlap(x)
    assert y.entry_i.tolist()==[10,30]
