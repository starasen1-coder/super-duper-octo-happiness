# Trader Skill Pipeline

## Цель
Воспроизводимый контур исследования XAUUSD M5 и подготовки MT5 EA:
1. OHLCV Bid/Ask + spread и проверка качества данных;
2. завершённая H1 structure без look-ahead;
3. M5 liquidity sweep → displacement/BOS → OB retest;
4. signal + conservative spread-aware execution;
5. backtest и разбор причин убытков;
6. chronological out-of-sample validation;
7. проверка устойчивости к spread, commission, slippage и задержке;
8. только после этого — перенос подтверждённой логики в MQL5.

## Реализовано в исследовательском контуре
- H1 структура становится доступной только после закрытия H1 свечи.
- build_retest_setups() ищет последовательность sweep → импульс с ATR/body-фильтром → пробой локальной структуры → возврат в последнюю противоположную свечу (OB) → подтверждение закрытием.
- Вход моделируется на открытии следующей M5 свечи после подтверждённого ретеста.
- Stop/Target рассчитываются от границ OB и заданного R:R.
- Исполнение учитывает spread и slippage; гэпы через SL/TP закрываются по первой доступной Bid, а не по недоступной цене уровня.
- Bid/Ask quote size не выдаётся за исполненный агрессивный объём.

## Пока не реализовано / не подтверждено
- FVG как отдельный фильтр и Volume Profile POC/VAH/VAL как фильтр сделки.
- Полноценный фильтр бокового рынка и сравнение его влияния на OOS.
- Tick-level Bid/Ask реконструкция исполнений на исходном историческом потоке.
- Commission, swap, latency и брокерский slippage на реальном AMarkets-специфичном наборе.
- Полная статистика по нескольким независимым временным holdout-периодам.
- MQL5 EA, компиляция MetaEditor и тест MT5 Strategy Tester.

## Правила
- MA не является обязательным источником сигнала.
- Не оптимизировать только Win Rate.
- Не считать котируемый объём исполненным order flow.
- Учитывать spread, commission и slippage.
- Разделять train/validation/test по времени.
- Не допускать look-ahead/repaint.
- Каждый эксперимент сохранять с параметрами и метриками.
- Не переносить стратегию в торговый EA до независимой проверки net expectancy и просадки.

## Метрики
Net Profit, Profit Factor, Expectancy/trade, Max Drawdown, Recovery Factor,
trade count, win rate, average win/loss, exposure, spread sensitivity,
out-of-sample degradation.

## Структура
data/ — исходные/очищенные данные
research/ — Python-анализ
backtest/ — результаты
mql5/ — будущий MT5 EA
tests/ — проверки
reports/ — отчёты
