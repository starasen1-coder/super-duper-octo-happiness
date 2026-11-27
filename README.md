# super-duper-octo-happiness

Проект содержит исходный MT5/LLM-прототип и отдельный исследовательский контур Agent Reach.

## Исследовательский контур (отдельный от MT5)

- `agent-reach/agent_reach/worker/` — сбор публичных GitHub-материалов через Agent Reach, нормализация и сохранение источников.
- `agent-reach/agent_reach/storage/` — SQLite, provenance, дедупликация и журнал заданий.
- `agent-reach/agent_reach/api/` — read-only API для сохранённых материалов.
- `security/skillspector/` — статическая проверка публичных Skills на фиксированном Git commit, fail-closed политика и реестр допуска расширений.
- `visual-reports/lemo_opuscar/` — манифест для ручной передачи отчёта в совместимую среду LEMO Opuscar.

Документы:
- [Архитектура VPS](docs/specs/2026-11-23-agent-reach-vps-design.md)
- [План реализации](docs/plans/2026-11-23-agent-reach-vps-implementation-plan.md)
- [Развёртывание research API](deploy/README.md)
- [Границы Agent Reach](docs/agent-reach-cloud.md)

## Граница безопасности

Исследовательский сервис не подключается к брокеру, MT5, торговым счетам или ордерам. API выдаёт только сохранённые записи. Первоначальный сбор использует публичный GitHub API без токенов и авторизованных сессий. Сторонние Skills допускаются только после проверки NVIDIA SkillSpector и точного совпадения записи в пустом по умолчанию реестре. VPS deployment требует отдельной подготовки доступа и проверки конфигурации.

## Существующий MT5/LLM прототип

- `proxy_server.py` — локальный FastAPI-прокси к LLM.
- `LLM_Advisor.mq5` — существующий советник-прототип.

Эти компоненты не являются частью исследовательского контура и не получают команды от Agent Reach, SkillSpector или LEMO Opuscar.
