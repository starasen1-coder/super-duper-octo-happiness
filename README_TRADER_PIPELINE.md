# Trader Skill Pipeline

## Цель
Воспроизводимый контур исследования XAUUSD M5 и подготовки MT5 EA:
1. OHLCV + spread;
2. H1 structure и M5 liquidity/sweep/impulse;
3. Volume Profile;
4. signal + execution;
5. backtest;
6. анализ сделок и причин убытков;
7. out-of-sample validation;
8. перенос проверенной логики в MQL5.

## Правила
- MA не является обязательным источником сигнала.
- Не оптимизировать только Win Rate.
- Учитывать spread, commission и slippage.
- Разделять train/validation/test по времени.
- Не допускать look-ahead/repaint.
- Каждый эксперимент сохранять с параметрами и метриками.

## Метрики
Net Profit, Profit Factor, Expectancy/trade, Max Drawdown, Recovery Factor,
trade count, win rate, average win/loss, exposure, spread sensitivity,
out-of-sample degradation.

## Структура
data/ — исходные/очищенные данные
research/ — Python-анализ
backtest/ — результаты
mql5/ — MT5 EA
tests/ — проверки
reports/ — отчёты
