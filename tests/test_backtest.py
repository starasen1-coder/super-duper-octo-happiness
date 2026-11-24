import pandas as pd
from research.backtest_xauusd_liquidity import run

def test_backtest_contract():
    idx=pd.date_range("2026-01-01",periods=1000,freq="5min",tz="UTC")
    b=100+pd.Series(range(1000),dtype=float)*.01
    df=pd.DataFrame({"datetime":idx,"open":b,"high":b+.2,"low":b-.2,"close":b+.05,"volume":1000})
    s,_=run(df)
    assert s["bars"]==1000 and "final" in s
