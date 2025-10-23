# 清理旧的回测数据并重新运行回测

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "清理和重新回测脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 删除旧的回测结果（可选）
Write-Host "步骤1: 清理旧的回测结果..." -ForegroundColor Yellow
if (Test-Path "user_data/backtest_results") {
    Write-Host "  发现旧的回测结果，正在清理..."
    Remove-Item -Path "user_data/backtest_results/*.zip" -Force -ErrorAction SilentlyContinue
    Write-Host "  ✓ 清理完成" -ForegroundColor Green
} else {
    Write-Host "  未发现旧结果" -ForegroundColor Gray
}
Write-Host ""

# 2. 运行回测
Write-Host "步骤2: 开始回测..." -ForegroundColor Yellow
Write-Host "  策略: Bollinger4h1hStructureStrategy" -ForegroundColor Gray
Write-Host "  时间范围: 2025-08-15 到 2025-10-04" -ForegroundColor Gray
Write-Host "  止损设置: stoploss = -0.01 (1%)" -ForegroundColor Gray
Write-Host ""

python -m freqtrade backtesting `
    --strategy Bollinger4h1hStructureStrategy `
    --config user_data/config_bollinger_4h1h.json `
    --timerange 20250815-20251004 `
    --export trades

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "回测完成！" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "请检查以下内容：" -ForegroundColor Yellow
Write-Host "1. 所有止损交易的亏损是否在 -1.0% 到 -1.5% 之间" -ForegroundColor White
Write-Host "2. 退出原因是否为 'stop_loss'（而非 'stoploss_1pct'）" -ForegroundColor White
Write-Host "3. 没有超过 -2% 的亏损（除非极端行情滑点）" -ForegroundColor White
Write-Host ""

