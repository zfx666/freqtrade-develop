# 止损问题修复指南

## 📋 问题描述

你的回测结果显示：
- `2025-08-15 12:00:00` 入场，`14:00:00` 平仓
- 亏损：**-2.22% (-4.382)**
- 退出原因：`stoploss_1pct`

**问题**：应该是1%止损，为什么亏损超过2%？

---

## 🔍 根本原因

### 1. **查看的是旧的回测结果**
你看到的交易记录是**之前运行回测时的数据**，当时的策略配置是：
- `stoploss = -0.05`（-5%硬止损）
- `custom_exit` 中有 `stoploss_pct` 参数（可能被设置为2%或更高）

### 2. **参数冲突**
策略中有一个 `stoploss_pct = DecimalParameter(0.005, 0.02, default=0.01, ...)` 参数：
- 如果之前运行过超参优化，可能生成了参数文件
- 这个参数可能覆盖了代码中的硬止损设置

### 3. **custom_exit 重复判断**
之前的代码在 `custom_exit` 中有重复的止损逻辑，导致：
- 硬止损（stoploss）没有生效
- custom_exit 中的逻辑在使用 `stoploss_pct` 参数
- 如果 `stoploss_pct` 被优化成了 2%，就会出现 -2.22% 的亏损

---

## ✅ 已实施的修复

### 修改1：设置硬止损为1%
```python
# 全局止损：设置为1%的实际止损值
# 注意：这是硬止损，会立即触发，不需要等K线收盘
stoploss = -0.01  # 1%止损
```

### 修改2：移除 stoploss_pct 参数
```python
# 注意：止损参数已移除，统一使用 stoploss = -0.01（1%硬止损）
# 不再使用可优化的止损参数，避免参数冲突

# 之前：
# stoploss_pct = DecimalParameter(0.005, 0.02, default=0.01, space="sell", optimize=True)
```

### 修改3：移除 custom_exit 中的重复止损
```python
# 注意：1%止损已由 stoploss = -0.01 自动处理，无需在这里判断
# Freqtrade 会自动在价格跌破1%时触发硬止损

# 之前有这段代码，现在已删除：
# if current_rate <= stop_loss_price:
#     return "stoploss_1pct"
```

---

## 🧪 如何重新回测

### 方法1：使用提供的脚本（推荐）
```powershell
.\clean_and_backtest.ps1
```

### 方法2：手动命令
```powershell
# 清理旧结果（可选）
Remove-Item -Path "user_data/backtest_results/*.zip" -Force

# 重新回测
python -m freqtrade backtesting `
    --strategy Bollinger4h1hStructureStrategy `
    --config user_data/config_bollinger_4h1h.json `
    --timerange 20250815-20251004 `
    --export trades
```

---

## 📊 预期结果

重新回测后，你应该看到：

### ✅ 正常的止损交易
| 入场价 | 止损价 | 实际出场价 | 亏损 | 原因 |
|--------|--------|------------|------|------|
| 4634.17 | 4587.83 | 4580 | -1.17% | 滑点（正常） |
| 4666.54 | 4619.88 | 4615 | -1.10% | 正常止损 |
| 4647.46 | 4600.59 | 4598 | -1.06% | 正常止损 |

### ❌ 不应该出现的情况
- 亏损超过 **-1.5%**（除非极端行情）
- 亏损达到 **-2%** 或更高
- 退出原因显示 `stoploss_1pct`（应该是 `stop_loss`）

---

## ⚠️ 为什么止损不是精确的 -1.00%？

### Freqtrade 止损机制
在回测中，Freqtrade 使用**K线的最低价 (low)** 来判断是否触及止损：

```
入场价格: 4634.17
止损价格: 4634.17 × 0.99 = 4587.83

K线数据:
- Open: 4634.17
- High: 4650.00
- Low: 4580.00  ← 触及止损
- Close: 4590.00

Freqtrade 判断：Low(4580) < 止损价(4587.83)
→ 触发止损
→ 使用 Low 价格作为平仓价
→ 实际亏损: (4580 - 4634.17) / 4634.17 = -1.17%
```

### 这是正常现象
- ✅ 模拟了真实市场的滑点
- ✅ 比精确 -1.00% 更真实
- ✅ 但**绝不会**达到 -2% 或 -5%（因为硬止损是 -1%）

---

## 🎯 验证清单

重新回测后，请检查：

- [ ] 所有止损交易亏损在 **-1.0% 到 -1.5%** 之间
- [ ] 退出原因显示为 `stop_loss`（而非 `stoploss_1pct`）
- [ ] 没有超过 **-2%** 的亏损
- [ ] `structure_weak` 退出的交易亏损可能更小

---

## 🔧 如果仍然出现问题

### 1. 检查是否有旧的参数文件
```powershell
Get-ChildItem -Path "user_data/strategies" -Filter "*.json"
```

如果有 `Bollinger4h1hStructureStrategy.json`，删除它：
```powershell
Remove-Item "user_data/strategies/Bollinger4h1hStructureStrategy.json"
```

### 2. 确认策略代码
检查 `user_data/strategies/Bollinger4h1hStructureStrategy.py` 第73行：
```python
stoploss = -0.01  # 必须是 -0.01
```

### 3. 查看回测日志
运行回测时，观察日志中是否有止损触发的记录。

### 4. 联系我
如果问题仍然存在，提供：
- 新的回测结果截图
- 回测命令和输出日志
- 策略文件的第70-75行代码

---

## 📝 总结

**修复前**：
- `stoploss = -0.05`（-5%）
- `custom_exit` 使用 `stoploss_pct` 参数（可能是2%）
- 结果：亏损 -2.22%

**修复后**：
- `stoploss = -0.01`（-1%硬止损）
- 移除 `stoploss_pct` 参数
- 移除 `custom_exit` 中的重复逻辑
- 预期结果：亏损 -1.0% 到 -1.5%

**现在需要做的**：
1. 运行 `.\clean_and_backtest.ps1` 重新回测
2. 查看新的交易记录
3. 验证止损是否正常工作

