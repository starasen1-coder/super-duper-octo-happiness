# Trader Skill Pipeline

## Цель
Воспроизводимый контур исследования XAUUSD M5 и подготовки MT5 EA:
1. синхронизация Bid/Ask OHLC + spread и аудит качества данных;
2. завершённая H1 structure без look-ahead;
3. M5 liquidity sweep → displacement/BOS → OB retest;
4. spread-aware исполнение LONG и SHORT;
5. последовательный backtest без перекрывающихся позиций;
6. разбор причин сделок и убытков;
7. chronological out-of-sample validation;
8. проверка устойчивости к spread, commission, slippage и задержке;
9. только после этого — перенос подтверждённой логики в MQL5.

## Реализовано в исследовательском контуре
- H1 структура становится доступной только после закрытия H1 свечи.
- build_retest_setups() ищет последовательность sweep → импульс с ATR/body-фильтром → пробой локальной структуры → возврат в последнюю противоположную свечу (OB) → подтверждение закрытием.
- Вход моделируется на открытии следующей M5 свечи после подтверждённого ретеста.
- Stop/Target рассчитываются от границ OB и заданного R:R.
- Отдельные execution-модели LONG и SHORT используют Ask/Bid соответственно.
- Гэпы через SL/TP закрываются по первой доступной котировке, а не по недоступной цене уровня.
- backtest_setups() выполняет сетапы последовательно, не открывает новую позицию на баре закрытия предыдущей и рассчитывает R-multiple.
- Bid/Ask quote size не выдаётся за исполненный агрессивный объём.

## Пока не реализовано / не подтверждено
- Сборка mid OHLC из синхронизированных Bid/Ask файлов и отдельная проверка spread на момент входа.
- Tick-level реконструкция цены входа/выхода и intrabar-порядка.
- FVG как отдельный фильтр и Volume Profile POC/VAH/VAL как фильтр сделки.
- Статистически проверенный фильтр бокового рынка и его OOS-эффект.
- Commission, swap, latency и брокерский slippage на AMarkets-специфичном наборе.
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
