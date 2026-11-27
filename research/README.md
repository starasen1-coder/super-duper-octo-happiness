# Research

Исследования должны быть воспроизводимыми. Исходные данные не изменяются; очистка создаёт отдельный набор.

## Признаки стратегии

- H1 BOS/CHoCH;
- M5 liquidity pool;
- sweep + close-back;
- impulse ATR-relative;
- candle body/range;
- displacement;
- Volume Profile POC/VAH/VAL;
- session;
- spread;
- distance to liquidity;
- risk/reward to next liquidity.

## Quote Liquidity

`research.quote_liquidity.aggregate_quote_liquidity` агрегирует Dukascopy tick quote updates в M5:
- средний объём, доступный на Bid и Ask;
- средний и медианный спред;
- число обновлений котировки;
- нормализованный Quote Liquidity Imbalance.

Это не executed trade flow: объём в котировке не является подтверждённым объёмом исполненных агрессивных покупок или продаж. Не переименовывать его в Trade Delta.

## Проверка преимущества

Каждый сигнал получает timestamp и outcome после фиксированного горизонта или TP/SL. Сравнение фильтра проводится на одинаковых базовых сигналах и одинаковых издержках:
1. стратегия без quote-liquidity фильтра;
2. та же стратегия с фильтром;
3. отдельно по временным OOS-сегментам.

Отчёт обязан включать число сделок, net expectancy, profit factor, максимальную просадку, средний win/loss, спред/проскальзывание и деградацию на OOS. Не выбирать фильтр только по win rate или результату обучающего периода.
