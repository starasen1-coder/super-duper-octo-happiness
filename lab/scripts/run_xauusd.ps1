param(
  [string]$Mt5Path = $env:MT5_PATH,
  [string]$From = "2022.01.01",
  [string]$To = "2026.01.01",
  [string]$Symbol = "XAUUSD",
  [string]$EA = "XAUUSD_Liquidity_Retest_v1",
  [int]$Deposit = 10000,
  [int]$Leverage = 10
)

$ErrorActionPreference = "Stop"

if (-not $Mt5Path) { throw "MT5_PATH is not set" }
$terminal = Join-Path $Mt5Path "terminal64.exe"
if (-not (Test-Path $terminal)) { throw "terminal64.exe not found" }

$cli = Get-Command "pp-mt5-backtester" -ErrorAction SilentlyContinue

if ($cli) {
  & $cli.Source run --ea $EA --symbol $Symbol --period M5 --from $From --to $To --model 4 --deposit $Deposit --currency USD --leverage $Leverage -o json
  if ($LASTEXITCODE -ne 0) { throw "Backtest failed: $LASTEXITCODE" }
  exit 0
}

Write-Host "pp-mt5-backtester is not installed."
Write-Host "Install: go install github.com/ek-labs/pp-mt5-backtester/cmd/pp-mt5-backtester@latest"
exit 2
