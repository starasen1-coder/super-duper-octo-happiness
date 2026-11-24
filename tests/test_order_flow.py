import pandas as pd
from research.order_flow import order_flow_features, order_flow_confirmation

def test_true_order_flow_uses_ask_minus_bid():
    df = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=3, freq="5min"),
        "open":[1,1,1], "high":[1,1,1], "low":[1,1,1], "close":[1,1,1],
        "volume":[10,20,30], "bid_volume":[8,5,20], "ask_volume":[12,15,25]
    })
    out = order_flow_features(df, mode="true")
    assert out["delta"].tolist() == [4,10,5]
    assert out["order_flow_mode"].eq("true").all()

def test_proxy_is_explicitly_labeled():
    df = pd.DataFrame({
        "open":[1,1], "high":[2,2], "low":[0,0], "close":[2,0], "volume":[10,20]
    })
    out = order_flow_features(df, mode="proxy")
    assert out["delta"].tolist() == [10,-20]
    assert out["order_flow_mode"].eq("proxy").all()

def test_confirmation_has_direction():
    df = pd.DataFrame({"delta":[5,-5], "delta_z":[2,-2]})
    assert order_flow_confirmation(df).tolist() == [1,-1]


def test_auto_mode_does_not_treat_ambiguous_bid_ask_sizes_as_trade_delta():
    df = pd.DataFrame({
        "open": [1.0, 1.0], "high": [2.0, 2.0], "low": [0.0, 0.0],
        "close": [2.0, 0.0], "volume": [10, 20],
        "bid_volume": [8, 5], "ask_volume": [12, 15],
    })
    out = order_flow_features(df, mode="auto")
    assert out["order_flow_mode"].eq("proxy").all()


def test_true_order_flow_requires_explicit_aggressor_trade_semantics():
    import pytest
    df = pd.DataFrame({
        "open": [1.0, 1.0], "high": [2.0, 2.0], "low": [0.0, 0.0],
        "close": [2.0, 0.0], "volume": [10, 20],
        "bid_volume": [8, 5], "ask_volume": [12, 15],
    })
    with pytest.raises(ValueError, match="aggressor_trade_volume"):
        order_flow_features(df, mode="true")
    df["volume_semantics"] = "aggressor_trade_volume"
    out = order_flow_features(df, mode="true")
    assert out["order_flow_mode"].eq("true").all()
