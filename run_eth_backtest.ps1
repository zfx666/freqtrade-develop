# ETH/USDT 完整回测流程
# 作者：AI助手
# 日期：2025-10-09

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ETH/USDT Bollinger4h1h策略回测流程" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 步骤1：下载ETH/USDT的1h和4h数据
Write-Host "步骤1：下载ETH/USDT历史数据..." -ForegroundColor Yellow
Write-Host "  - 时间范围：2024年1月1日 至 2024年10月10日" -ForegroundColor Gray
python -m freqtrade download-data --config user_data/config_bollinger_4h1h.json --timeframe 1h 4h --timerange 20240101-20241010

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 数据下载失败！" -ForegroundColor Red
    exit 1
}
Write-Host "✓ 数据下载完成" -ForegroundColor Green
Write-Host ""

# 步骤2：验证下载的数据
Write-Host "步骤2：验证下载的数据..." -ForegroundColor Yellow
python -m freqtrade list-data --config user_data/config_bollinger_4h1h.json
Write-Host ""

# 步骤3：运行回测
Write-Host "步骤3：运行回测..." -ForegroundColor Yellow
Write-Host "  - 交易对：ETH/USDT" -ForegroundColor Gray
Write-Host "  - 策略：Bollinger4h1hStructureStrategy" -ForegroundColor Gray
Write-Host "  - 时间范围：2024-01-01 至 2024-10-10" -ForegroundColor Gray
python -m freqtrade backtesting --config user_data/config_bollinger_4h1h.json --strategy Bollinger4h1hStructureStrategy --timerange 20240101-20241010 --export trades

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 回测失败！" -ForegroundColor Red
    exit 1
}
Write-Host "✓ 回测完成" -ForegroundColor Green
Write-Host ""

# 步骤4：生成分析CSV
Write-Host "步骤4：生成详细分析CSV..." -ForegroundColor Yellow
python generate_eth_analysis.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ CSV生成失败！" -ForegroundColor Red
    exit 1
}
Write-Host "✓ 分析CSV生成完成" -ForegroundColor Green
Write-Host ""

# 步骤5：查看回测结果
Write-Host "步骤5：查看回测结果..." -ForegroundColor Yellow
python -m freqtrade backtesting-show

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  回测流程完成！" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "生成的文件：" -ForegroundColor Green
Write-Host "  1. user_data\backtest_results\      - 回测结果" -ForegroundColor Gray
Write-Host "  2. user_data\debug\                 - 策略调试CSV" -ForegroundColor Gray
Write-Host "  3. eth_analysis_full.csv            - 完整分析数据" -ForegroundColor Gray
Write-Host "  4. eth_analysis_armed.csv           - Armed时段数据（如有）" -ForegroundColor Gray
Write-Host "  5. eth_analysis_entries.csv         - 入场信号详情（如有）" -ForegroundColor Gray
Write-Host ""





