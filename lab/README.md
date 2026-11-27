# XAUUSD Backtest Agent Pipeline

Цель: воспроизводимо прогонять каждую версию EA через compile -> MT5 Strategy Tester -> report -> metrics -> visual diagnostics -> independent review -> next patch.

Компоненты:
- XAUUSD_Liquidity_Retest_v1.mq5 — текущий EA.
- indicators/XAUUSD_Liquidity_Diagnostic.mq5 — визуальная разметка structure/sweep/impulse.
- screeners/XAUUSD_Setup_Screener.mq5 — скринер setup-условий без открытия сделок.
- agents/orchestrator.md — координатор.
- agents/strategy_reviewer.md — независимая проверка логики.
- agents/backtest_analyst.md — анализ отчёта MT5.
- agents/robustness_reviewer.md — проверка устойчивости и OOS.
- config/xauusd_m5.json — единая конфигурация.
- scripts/run_xauusd.ps1 — запуск теста на Windows/MT5.
- .github/workflows/xauusd-backtest.yml — запуск через self-hosted Windows runner.

Важно: GitHub-hosted Linux runner не запускает MT5. Для реального прогона нужен Windows self-hosted runner с MT5, авторизованным брокерским аккаунтом и загруженной историей XAUUSD.

В качестве инфраструктуры можно использовать open-source mt5-agent-toolkit и pp-mt5-backtester. Их README заявляют headless compile/backtest и MIT license; перед обновлением версий проверять license/commit.

Критерии результата:
Net Profit, Profit Factor, Max Drawdown %, trades, win rate, expectancy, average win/loss, consecutive losses, stability by month/quarter, IS/OOS, trend/flat split, session split, NO TRADE reasons.

Главный критерий: воспроизводимое преимущество после издержек без систематических входов во флете. Максимизация Net Profit сама по себе не считается успехом.
