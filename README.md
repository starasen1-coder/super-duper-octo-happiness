# super-duper-octo-happiness

Торговый советник (EA) для MT5 + локальный прокси к LLM.

## Установка
1. VS Code: открыть папку, принять рекомендуемые расширения (`.vscode/extensions.json`).
2. `python -m venv .venv`, активировать, затем `pip install -r requirements.txt`.
3. Для ML-исследований отдельно: `pip install -r requirements-ml.txt`.
4. Скопировать `.env.example` в `.env` и вписать ключ API. Файл `.env` в git не попадает.
5. MT5: Сервис → Настройки → Советники → «Разрешить WebRequest», добавить `http://127.0.0.1:8000`.

## Структура
- `LLM_Advisor.mq5` — текущий MT5 EA-каркас.
- `proxy_server.py` — FastAPI-прокси к LLM.
- `ml/edge_model.py` — PyTorch LSTM-фильтр для оценки вероятности исхода уже найденного liquidity/structure setup.
- `ml/walk_forward.py` — expanding walk-forward валидация без случайного перемешивания.
- `ml/README.md` — схема признаков, target и правила защиты от leakage.
- `requirements-ml.txt` — отдельные зависимости для ML-исследований.

## Принцип ML-фильтра
Нейросеть не генерирует сделки самостоятельно. Сначала детерминированный модуль
находит setup по структуре/ликвидности, затем модель оценивает его вероятность.
Основной критерий сравнения — out-of-sample expectancy после spread/commission/slippage,
а не accuracy.

## Источник идей
Для выбора компонентов просмотрен каталог TopDeepLearning:
https://github.com/aymericdamien/TopDeepLearning
Использованы общие инженерные идеи PyTorch/sequence modeling и time-series validation;
код из сторонних репозиториев в проект не копировался.


## Offline research harness

`ml/research.py` builds a defined OHLCV sweep/impulse benchmark and reports R-multiple metrics. Run `python -m unittest discover -s tests -v` before experiments. This first harness is not yet execution-equivalent to the MT5 EA; see `ml/README.md` for scope, input format and limitations. Historical XAUUSD data and out-of-fold ML predictions are required before any strategy comparison or edge claim.


## XAUUSD M5 market data

The repository includes a Dukascopy Bid/Ask M5 downloader and a data-quality validator. See `ml/README.md` for the 2015–2025 download commands, spread units, quote-side execution assumptions, and source limitations. Raw history is downloaded locally rather than committed as a large binary dataset.
