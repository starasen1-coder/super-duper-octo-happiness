# super-duper-octo-happiness

Торговый советник (EA) для MT5 + локальный прокси к LLM.

## Установка
1. VS Code: открыть папку, принять рекомендуемые расширения (`.vscode/extensions.json`).
2. `python -m venv .venv`, активировать, затем `pip install -r requirements.txt`.
3. Скопировать `.env.example` в `.env` и вписать ключ API. Файл `.env` в git не попадает.
4. MT5: Сервис → Настройки → Советники → «Разрешить WebRequest», добавить `http://127.0.0.1:8000`.

## Структура (план)
- `proxy/` — FastAPI-сервер, вызывает модель, возвращает JSON
- `mql5/` — код советника
