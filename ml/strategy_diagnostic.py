"""Offline XAUUSD M5 liquidity-sweep diagnostic; no broker or order routing."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd


def detect_sweeps(d: pd.DataFrame, lookback: int = 36) -> pd.DataFrame:
    if '_segment' in d.columns:
        prior_low = d.groupby('_segment', sort=False)['low'].transform(lambda x: x.rolling(lookback, min_periods=lookback).min().shift(1))
        prior_high = d.groupby('_segment', sort=False)['high'].transform(lambda x: x.rolling(lookback, min_periods=lookback).max().shift(1))
    else:
        prior_low = d['low'].rolling(lookback, min_periods=lookback).min().shift(1)
        prior_high = d['high'].rolling(lookback, min_periods=lookback).max().shift(1)
    out = pd.DataFrame(index=d.index)
    out['sweep_level_long'] = prior_low
    out['sweep_level_short'] = prior_high
    out['long_sweep'] = (d['low'] < prior_low) & (d['close'] > prior_low)
    out['short_sweep'] = (d['high'] > prior_high) & (d['close'] < prior_high)
    return out


def classify_impulse(d: pd.DataFrame, atr_multiple: float = 1.4, body_fraction: float = .65) -> pd.DataFrame:
    span = (d['high'] - d['low']).replace(0, np.nan)
    body = (d['close'] - d['open']).abs()
    strong = (span >= atr_multiple * d['atr']) & ((body / span) >= body_fraction)
    out = pd.DataFrame(index=d.index)
    out['bull_impulse'] = strong & (d['close'] > d['open'])
    out['bear_impulse'] = strong & (d['close'] < d['open'])
    return out


def _h1_bias(m5: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    h = m5[['mid_open','mid_high','mid_low','mid_close']].resample('1h').agg(
        open=('mid_open','first'), high=('mid_high','max'), low=('mid_low','min'), close=('mid_close','last'))
    # Three-left/three-right fractals become known only after three subsequent H1 bars.
    ph = h['high'].where((h['high'] > h['high'].shift(1)) & (h['high'] > h['high'].shift(2)) &
                         (h['high'] > h['high'].shift(3)) & (h['high'] >= h['high'].shift(-1)) &
                         (h['high'] >= h['high'].shift(-2)) & (h['high'] >= h['high'].shift(-3))).shift(3)
    pl = h['low'].where((h['low'] < h['low'].shift(1)) & (h['low'] < h['low'].shift(2)) &
                        (h['low'] < h['low'].shift(3)) & (h['low'] <= h['low'].shift(-1)) &
                        (h['low'] <= h['low'].shift(-2)) & (h['low'] <= h['low'].shift(-3))).shift(3)
    last_hi, last_lo = ph.ffill(), pl.ffill()
    state = np.zeros(len(h), dtype=np.int8)
    cur = 0
    for i, (close, hi, lo) in enumerate(zip(h['close'].to_numpy(), last_hi.to_numpy(), last_lo.to_numpy())):
        if np.isfinite(hi) and close > hi:
            cur = 1
        elif np.isfinite(lo) and close < lo:
            cur = -1
        state[i] = cur
    net = (h['close'] - h['close'].shift(12)).abs()
    path = h['close'].diff().abs().rolling(12).sum()
    er = net / path.replace(0, np.nan)
    bias = pd.DataFrame({'bias': state, 'er': er.to_numpy()}, index=h.index).shift(1)
    m = pd.merge_asof(
        pd.DataFrame(index=m5.index).reset_index(names='timestamp'),
        bias.reset_index(names='timestamp'), on='timestamp', direction='backward')
    return (pd.Series(m['bias'].fillna(0).to_numpy(), index=m5.index),
            pd.Series(m['er'].to_numpy(), index=m5.index))


def prepare(path: str | Path) -> pd.DataFrame:
    d = pd.read_csv(path, parse_dates=['timestamp']).set_index('timestamp').sort_index()
    for side in ('bid', 'ask'):
        for part in ('open', 'high', 'low', 'close'):
            d[f'{side}_{part}'] = pd.to_numeric(d[f'{side}_{part}'], errors='coerce')
    for part in ('open', 'high', 'low', 'close'):
        d[f'mid_{part}'] = (d[f'bid_{part}'] + d[f'ask_{part}']) / 2
    # Reset all M5 rolling state after any timestamp discontinuity; never bridge sessions.
    d['_segment'] = (d.index.to_series().diff().dt.total_seconds().div(60).fillna(5).gt(5)).cumsum().to_numpy()
    prev_close = d.groupby('_segment', sort=False)['mid_close'].shift(1)
    tr = pd.concat([(d.mid_high-d.mid_low), (d.mid_high-prev_close).abs(),
                    (d.mid_low-prev_close).abs()], axis=1).max(axis=1)
    d['atr'] = tr.groupby(d['_segment'], sort=False).transform(lambda x: x.rolling(14, min_periods=14).mean())
    return d


def build_signals(d: pd.DataFrame, use_h1_filter: bool = True, use_er_filter: bool = True) -> pd.DataFrame:
    sw = detect_sweeps(d.rename(columns={'mid_high':'high','mid_low':'low','mid_close':'close'}), 36)
    imp = classify_impulse(d.rename(columns={'mid_open':'open','mid_high':'high','mid_low':'low','mid_close':'close'}), 1.4, .65)
    bias, er = _h1_bias(d)
    out = []
    prev_hi = d.groupby('_segment', sort=False)['mid_high'].transform(lambda x: x.rolling(5, min_periods=5).max().shift(1))
    prev_lo = d.groupby('_segment', sort=False)['mid_low'].transform(lambda x: x.rolling(5, min_periods=5).min().shift(1))
    bull = np.flatnonzero((imp.bull_impulse & (d.mid_close > prev_hi)).fillna(False).to_numpy())
    bear = np.flatnonzero((imp.bear_impulse & (d.mid_close < prev_lo)).fillna(False).to_numpy())
    candidates = {int(i): 1 for i in bull}
    candidates.update({int(i): -1 for i in bear})
    for i in sorted(candidates):
        if i < 40 or i >= len(d)-20:
            continue
        direction = candidates[i]
        sweep_i = None
        for j in range(i-1, max(i-4, 0), -1):
            if direction == 1 and bool(sw.long_sweep.iloc[j]):
                sweep_i = j
                break
            if direction == -1 and bool(sw.short_sweep.iloc[j]):
                sweep_i = j
                break
        if sweep_i is None or d._segment.iloc[sweep_i] != d._segment.iloc[i]:
            continue
        if use_h1_filter and int(bias.iloc[i]) != direction:
            continue
        if use_er_filter and (not np.isfinite(er.iloc[i]) or er.iloc[i] < .25):
            continue
        ob = None
        for k in range(i-1, max(sweep_i-1, i-6), -1):
            if d._segment.iloc[k] != d._segment.iloc[i]:
                break
            bearish = d.mid_close.iloc[k] < d.mid_open.iloc[k]
            bullish = d.mid_close.iloc[k] > d.mid_open.iloc[k]
            if (direction == 1 and bearish) or (direction == -1 and bullish):
                ob = k
                break
        if ob is None:
            continue
        entry = (d.mid_high.iloc[ob] + d.mid_low.iloc[ob]) / 2
        stop = float(d.mid_low.iloc[sweep_i] if direction == 1 else d.mid_high.iloc[sweep_i])
        if (direction == 1 and not stop < entry) or (direction == -1 and not stop > entry):
            continue
        out.append({'signal_i': i, 'sweep_i': sweep_i, 'ob_i': ob, 'direction': direction,
                    'entry': float(entry), 'stop': stop, 'atr': float(d.atr.iloc[i]),
                    'h1_er': float(er.iloc[i]) if np.isfinite(er.iloc[i]) else np.nan})
    return pd.DataFrame(out)


def simulate(d: pd.DataFrame, signals: pd.DataFrame, rr: float = 2.0,
             max_wait: int = 12, max_hold: int = 48) -> pd.DataFrame:
    trades = []
    occupied_until = -1
    for s in signals.itertuples(index=False):
        if s.signal_i <= occupied_until:
            continue
        direction, entry, stop = int(s.direction), float(s.entry), float(s.stop)
        risk = entry-stop if direction == 1 else stop-entry
        if risk <= 0 or not np.isfinite(risk):
            continue
        target = entry + direction * rr * risk
        fill_i = None
        for k in range(s.signal_i+1, min(s.signal_i+1+max_wait, len(d))):
            touched = (d.ask_low.iloc[k] <= entry <= d.ask_high.iloc[k]) if direction == 1 else (d.bid_low.iloc[k] <= entry <= d.bid_high.iloc[k])
            if touched:
                fill_i = k
                break
        if fill_i is None:
            continue
        exit_i = None
        outcome = 'TIME'
        exit_price = None
        for k in range(fill_i, min(fill_i+max_hold, len(d))):
            if direction == 1:
                hit_sl, hit_tp = d.bid_low.iloc[k] <= stop, d.bid_high.iloc[k] >= target
            else:
                hit_sl, hit_tp = d.ask_high.iloc[k] >= stop, d.ask_low.iloc[k] <= target
            # Conservative: stop first if both levels occur within the same M5 bar.
            if hit_sl:
                exit_i, outcome, exit_price = k, 'SL', stop
                break
            if hit_tp:
                exit_i, outcome, exit_price = k, 'TP', target
                break
        if exit_i is None:
            exit_i = min(fill_i+max_hold-1, len(d)-1)
            exit_price = float(d.bid_close.iloc[exit_i] if direction == 1 else d.ask_close.iloc[exit_i])
        r_multiple = (exit_price-entry) * direction / risk
        trades.append({'year': d.index[fill_i].year, 'signal_time': d.index[s.signal_i].isoformat(),
                       'entry_time': d.index[fill_i].isoformat(), 'exit_time': d.index[exit_i].isoformat(),
                       'direction': direction, 'entry_quote': entry, 'stop_quote': stop,
                       'target_quote': target, 'exit_quote': exit_price, 'result': outcome,
                       'r_multiple': r_multiple,
                       'spread_entry': float(d.spread_mean_ohlc.iloc[fill_i]) if 'spread_mean_ohlc' in d else float(d.spread_open.iloc[fill_i]),
                       'h1_er': s.h1_er})
        occupied_until = exit_i
    return pd.DataFrame(trades)


def summarize(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {'trades': 0, 'win_rate': None, 'profit_factor': None, 'expectancy_r': None, 'max_drawdown_r': None}
    r = trades.r_multiple.astype(float)
    equity = r.cumsum()
    dd = equity - equity.cummax()
    gains, losses = r[r > 0].sum(), -r[r < 0].sum()
    return {'trades': int(len(r)), 'win_rate': float((r > 0).mean()),
            'profit_factor': float(gains/losses) if losses > 0 else None,
            'expectancy_r': float(r.mean()), 'max_drawdown_r': float(dd.min()),
            'total_r': float(r.sum()), 'median_entry_spread': float(trades.spread_entry.median()),
            'p95_entry_spread': float(trades.spread_entry.quantile(.95))}


def run(path: str, output_dir: str) -> dict:
    d = prepare(path)
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    variants = {'sweep_impulse_only': (False, False), 'h1_structure': (True, False),
                'h1_structure_plus_flat_filter': (True, True)}
    results, yearly = {}, []
    for name, (h1, er) in variants.items():
        signals = build_signals(d, h1, er)
        trades = simulate(d, signals)
        trades.to_csv(outdir/f'{name}_trades.csv', index=False)
        results[name] = summarize(trades)
        if not trades.empty:
            for year, group in trades.groupby('year'):
                yearly.append({'variant': name, 'year': int(year), **summarize(group)})
    splits = {'2015-2021_in_sample': (2015, 2021), '2022-2025_holdout': (2022, 2025)}
    split_results = {}
    for split_name, (y0, y1) in splits.items():
        split_results[split_name] = {}
        for variant_name in variants:
            file = outdir/f'{variant_name}_trades.csv'
            trades = pd.read_csv(file) if file.exists() else pd.DataFrame()
            subset = trades[(trades.year >= y0) & (trades.year <= y1)] if not trades.empty else trades
            split_results[split_name][variant_name] = summarize(subset)
    report = {'dataset_rows': int(len(d)), 'first_utc': d.index.min().isoformat(),
              'last_utc': d.index.max().isoformat(),
              'method': 'M5 rolling state resets at every timestamp gap; H1 confirmed fractal BOS state; M5 36-bar sweep; next-1-to-3-bar ATR impulse (>=1.4 ATR, body >=65%); 5-bar structure break; last opposing candle midpoint retest; 2R target; 12-bar limit expiry; 48-bar max hold; conservative stop-first intrabar ordering; quote-side spread included.',
              'limitations': ['Reference Dukascopy-derived quotes, not broker-specific fills.',
                              'Bid/Ask bars are separately aggregated; intrabar ordering is unknown.',
                              'No commission, swap, slippage beyond quoted spread, or latency model.',
                              'H1 fractals use right-side confirmation and are delayed; only completed H1 state is mapped to M5.',
                              'This is a diagnostic, not evidence of a deployable edge.'],
              'variants': results, 'yearly': yearly, 'period_splits': split_results}
    (outdir/'strategy_diagnostic.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    lines = ['# XAUUSD M5 strategy diagnostic 2015–2025', '',
             'This is an offline research diagnostic, not a live-trading recommendation.', '',
             report['method'], '', '## Aggregate results', '',
             '| Variant | Trades | Win rate | PF | Expectancy (R) | Max DD (R) | Total R |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for name, value in results.items():
        lines.append(f"| {name} | {value['trades']} | {value['win_rate'] if value['win_rate'] is not None else '—'} | {value['profit_factor'] if value['profit_factor'] is not None else '—'} | {value['expectancy_r'] if value['expectancy_r'] is not None else '—'} | {value['max_drawdown_r'] if value['max_drawdown_r'] is not None else '—'} | {value.get('total_r','—')} |")
    lines += ['', '## Time-split results (fixed rules, no parameter tuning)', '',
              '| Period | Variant | Trades | Win rate | PF | Expectancy (R) | Total R |',
              '|---|---|---:|---:|---:|---:|---:|']
    for period, variant_values in split_results.items():
        for name, value in variant_values.items():
            lines.append(f"| {period} | {name} | {value['trades']} | {value['win_rate'] if value['win_rate'] is not None else '—'} | {value['profit_factor'] if value['profit_factor'] is not None else '—'} | {value['expectancy_r'] if value['expectancy_r'] is not None else '—'} | {value.get('total_r','—')} |")
    lines += ['', '## Year-by-year results', '',
              '| Variant | Year | Trades | Win rate | PF | Expectancy (R) | Total R |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for item in yearly:
        lines.append(f"| {item['variant']} | {item['year']} | {item['trades']} | {item['win_rate']:.3f} | {item['profit_factor'] if item['profit_factor'] is not None else '—'} | {item['expectancy_r']:.3f} | {item['total_r']:.2f} |")
    lines += ['', '## Limitations'] + [f'- {item}' for item in report['limitations']]
    (outdir/'strategy_diagnostic.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', required=True)
    parser.add_argument('--output-dir', default='reports/xauusd_strategy_2015_2025')
    args = parser.parse_args()
    print(json.dumps(run(args.csv, args.output_dir), indent=2))
