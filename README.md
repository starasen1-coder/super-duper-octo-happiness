# super-duper-octo-happiness

Торговый советник (EA) для MT5 + локальный прокси к LLM.

## Установка

1. Установить Python 3.11 и Node.js 22 LTS (вместе с npm).
2. VS Code: открыть папку, принять рекомендуемые расширения (`.vscode/extensions.json`).
3. Создать окружение Python: `python -m venv .venv`, активировать его.
4. Установить базовые зависимости: `python -m pip install -r requirements.txt`.
5. Для работы с историческими котировками: `python -m pip install -r requirements-data.txt`.
6. Для ML-исследований отдельно: `python -m pip install -r requirements-ml.txt`.
7. Скопировать `.env.example` в `.env` и вписать ключ API. Файл `.env` в git не попадает.
8. MT5: Сервис → Настройки → Советники → «Разрешить WebRequest», добавить `http://127.0.0.1:8000`.

Версии среды фиксируются в `.nvmrc` (Node.js) и `.python-version` (Python).
Команды для подготовки среды, загрузки котировок и проверки CSV вынесены в `package.json`.

## Структура

- `LLM_Advisor.mq5` — текущий MT5 EA-каркас.
- `proxy_server.py` — FastAPI-прокси к LLM.
- `ml/edge_model.py` — PyTorch LSTM-фильтр для оценки вероятности исхода уже найденного liquidity/structure setup.
- `ml/walk_forward.py` — expanding walk-forward валидация без случайного перемешивания.
- `ml/README.md` — схема признаков, target и правила защиты от leakage.
- `requirements-data.txt` — минимальные зависимости для загрузки и проверки CSV.
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

`ml/research.py` builds a defined OHLCV sweep/impulse benchmark and reports R-multiple metrics. Run `npm run test:python` before experiments. This first harness is not yet execution-equivalent to the MT5 EA; see `ml/README.md` for scope, input format and limitations. Historical XAUUSD data and out-of-fold ML predictions are required before any strategy comparison or edge claim.

## XAUUSD M5 market data

The repository includes a Dukascopy Bid/Ask M5 downloader and a data-quality validator. See `ml/README.md` and `data/README.md` for the 2015–2025 download commands, spread units, quote-side execution assumptions, and source limitations. Raw history is downloaded locally rather than committed as a large dataset.
