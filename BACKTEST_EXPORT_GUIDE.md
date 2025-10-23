# 📊 回测数据导出指南

## 功能说明

策略 `Bollinger4h1hStructureStrategy` 现已支持在回测时自动导出每小时的详细指标数据和入场信号，方便后续分析。

---

## 📁 导出的数据内容

### 1. **基础数据**
- **1h K线数据**: 时间、开盘价、最高价、最低价、收盘价、成交量
- **4h K线数据**: 4小时周期的OHLCV数据

### 2. **技术指标**
- **1h布林带**: 上轨、中轨、下轨
- **4h布林带**: 上轨、中轨、下轨、宽度

### 3. **策略信号**
- **4h Armed状态**:
  - `宽度达标4h`: 布林带宽度是否符合缩口条件
  - `上穿上轨4h`: 价格是否突破布林上轨
  - `跌破下轨4h`: 价格是否跌破布林下轨
  - `Armed当根4h`: 当前4h是否触发Armed
  - `Armed持续4h`: Armed粘性状态是否激活

- **1h结构信号**:
  - `结构高`: 缠论结构合并后的高点
  - `结构低`: 缠论结构合并后的低点
  - `结构类型`: 1=高点, -1=低点, 0=未定义
  - `HLH信号`: 是否出现高-低-高形态

### 4. **入场确认详情** ⭐ **新增**
- **`入场信号`**: 是否满足基本入场条件（Armed + HLH）
- **`入场确认结果`**: 待确认 / 通过 / 拒绝
- **`拒绝原因`**: 如果被拒绝，显示具体原因
  - 价格太接近止损价
  - 价格急跌中
  - 结构已转弱
  - 在冷却期内
- **`价格变化率`**: 当前价格相对前一根K线的变化百分比
- **`止损距离`**: 当前价格到1%止损价的距离
- **`结构状态`**: strong / weak / unknown

### 5. **控制信号**
- **`预热期`**: 是否在预热期（前80小时）
- **`入场评估`**: 是否满足Armed + HLH + 非预热期

---

## 🚀 使用方法

### 步骤1：运行回测

```powershell
# 基本回测命令（使用默认时间范围）
freqtrade backtesting `
  --strategy Bollinger4h1hStructureStrategy `
  --config user_data/config_bollinger_4h1h.json `
  --export trades

# 指定时间范围回测（推荐）
freqtrade backtesting `
  --strategy Bollinger4h1hStructureStrategy `
  --config user_data/config_bollinger_4h1h.json `
  --timerange 20241010-20251010 `
  --export trades
```

### 步骤2：查找导出的CSV文件

回测完成后，会在 `user_data/debug/` 目录下生成CSV文件：

```
user_data/debug/BollingerHLH_<交易对>_1h_full.csv
```

例如：
```
user_data/debug/BollingerHLH_BTC_USDT_1h_full.csv
user_data/debug/BollingerHLH_ETH_USDT_1h_full.csv
```

### 步骤3：打开CSV文件分析

使用Excel、WPS表格或任何支持CSV的工具打开文件。

---

## 📊 CSV文件列说明

### 中文表头对照表

| 中文列名 | 英文列名 | 说明 |
|---------|---------|------|
| **基础数据** |
| 时间 | date | 1h K线时间戳 |
| 开盘价 | open | 1h开盘价 |
| 最高价 | high | 1h最高价 |
| 最低价 | low | 1h最低价 |
| 收盘价 | close | 1h收盘价 |
| 成交量 | volume | 1h成交量 |
| **1h布林带** |
| 布林上轨1h | bb_upper | 1h布林上轨 |
| 布林中轨1h | bb_middle | 1h布林中轨 |
| 布林下轨1h | bb_lower | 1h布林下轨 |
| **4h数据** |
| 4小时起始时间 | date_4h | 4h周期起始时间 |
| 4小时开盘价 | open_4h | 4h开盘价 |
| 4小时最高价 | high_4h | 4h最高价 |
| 4小时最低价 | low_4h | 4h最低价 |
| 4小时收盘价 | close_4h | 4h收盘价 |
| 4小时成交量 | volume_4h | 4h成交量 |
| **4h布林带** |
| 布林上轨4h | bb_upper_4h | 4h布林上轨 |
| 布林中轨4h | bb_middle_4h | 4h布林中轨 |
| 布林下轨4h | bb_lower_4h | 4h布林下轨 |
| 布林宽度4h | bb_width_4h | (上轨-下轨)/中轨 |
| **4h条件判断** |
| 宽度达标4h | is_width_ok_4h | 宽度≤4.5%（缩口） |
| 上穿上轨4h | is_breakout_4h | 收盘价>上轨 |
| 跌破下轨4h | is_below_lower_4h | 收盘价≤下轨 |
| Armed当根4h | is_armed_4h | 当根触发Armed |
| Armed持续4h | armed_active_4h | 粘性Armed状态 |
| **1h结构** |
| 结构高 | structure_high | 缠论合并后的高点 |
| 结构低 | structure_low | 缠论合并后的低点 |
| 结构类型 | structure_type | 1=高/-1=低/0=未定义 |
| HLH信号 | hlh_signal | 高-低-高形态 |
| **入场控制** |
| 预热期 | is_warmup | 是否在预热期 |
| 入场评估 | debug_entry_eval | Armed+HLH+非预热 |
| 入场信号 | enter_long | 最终入场信号(1=是) |
| **入场确认详情** ⭐ |
| 入场确认结果 | entry_confirm_result | 待确认/通过/拒绝 |
| 拒绝原因 | entry_reject_reason | 具体拒绝原因 |
| 价格变化率 | price_change_pct | 相对前一根的变化% |
| 止损距离 | stop_loss_distance | 到止损价的距离% |
| 结构状态 | structure_status | strong/weak/unknown |

---

## 🔍 数据分析示例

### 1. 筛选所有入场信号

在Excel中筛选 `入场信号 = 1` 的行，查看所有触发入场的时刻。

### 2. 查看入场确认详情

对于 `入场信号 = 1` 的行，查看：
- **`入场确认结果`**: 看是否通过最终确认
- **`拒绝原因`**: 如果被拒绝，了解原因
- **`价格变化率`**: 检查入场时的价格动量
- **`止损距离`**: 确认是否有足够的止损空间
- **`结构状态`**: 验证结构是否强势

### 3. 分析Armed状态持续时间

筛选 `Armed持续4h = True` 的连续行，计算Armed状态的平均持续时长。

### 4. 检查HLH触发频率

统计 `HLH信号 = True` 的行数，了解HLH形态的出现频率。

### 5. 对比布林带宽度

创建图表，绘制 `布林宽度4h` 的时间序列，观察波动规律。

---

## 💡 常见问题

### Q1: CSV文件在哪里？
**A**: 在 `user_data/debug/` 目录下，文件名格式为 `BollingerHLH_<交易对>_1h_full.csv`

### Q2: 为什么有些行的 `入场信号 = 1` 但 `入场确认结果` 为空？
**A**: `入场信号 = 1` 只表示满足了基本条件（Armed + HLH），但还需要通过 `confirm_trade_entry` 的额外检查。在回测数据导出时，这些额外检查的结果在 `populate_entry_trend` 阶段只能预判（显示为"待确认"），实际确认发生在订单执行时。

### Q3: 如何判断一个入场信号是否真正被执行？
**A**: 需要结合 `user_data/backtest_results/*-trades.csv` 文件，对照时间和价格，查看是否有对应的真实交易记录。

### Q4: `价格变化率` 是负数什么意思？
**A**: 负数表示价格相对前一根K线下跌。例如 `-0.008` 表示下跌了0.8%。

### Q5: `结构状态` 为 `unknown` 是什么原因？
**A**: 通常是因为：
- 结构低点为0或NaN（结构未初始化）
- 在预热期内（前80小时）
- Armed状态刚触发，还没有足够的历史数据

---

## 📈 Excel分析技巧

### 技巧1：筛选有效入场点

```
1. 点击"数据" → "筛选"
2. 筛选 "入场信号" = 1
3. 筛选 "入场确认结果" = "待确认" 或 "通过"
4. 筛选 "预热期" = FALSE
```

### 技巧2：创建价格走势图

```
1. 选中 "时间" 和 "收盘价" 列
2. 插入 → 折线图
3. 添加 "布林上轨1h" 和 "布林下轨1h" 到图表
4. 用不同颜色标记 "Armed持续4h" = True 的区域
```

### 技巧3：计算Armed持续时长

```
1. 创建辅助列 "Armed开始"
2. 公式: =IF(AND(Armed持续4h=TRUE, OFFSET(Armed持续4h,-1,0)=FALSE), 时间, "")
3. 创建辅助列 "Armed结束"
4. 公式: =IF(AND(Armed持续4h=FALSE, OFFSET(Armed持续4h,-1,0)=TRUE), 时间, "")
5. 计算时间差
```

### 技巧4：统计入场信号分布

```
1. 创建透视表
2. 行：时间（按月分组）
3. 值：入场信号（计数）
4. 查看每月的入场机会数量
```

---

## 🎯 下一步

1. **运行回测**，生成CSV文件
2. **打开Excel**，分析导出的数据
3. **识别模式**，找出最佳入场时机的共同特征
4. **优化参数**，调整策略的阈值设置

祝回测顺利！🚀




