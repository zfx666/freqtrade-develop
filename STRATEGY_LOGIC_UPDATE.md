# Bollinger4h1hStructureStrategy 逻辑更新说明

## 修改内容

### 修改前（错误逻辑）
- ❌ 按4h固定分组：00:00-04:00一组，04:00-08:00一组
- ❌ 每个4h区间独立计算HLH
- ❌ 只在固定的4个1h内检测HLH
- ❌ 不会跨4h区间累积

### 修改后（正确逻辑）
- ✅ 从Armed触发点开始动态累积
- ✅ 每个1h收盘后累积检测
- ✅ 可以跨4h区间
- ✅ Armed失效时重置累积

## 详细流程示例

### 场景：2点Armed触发

**时间线：**
```
00:00 - Armed=False, 跳过
01:00 - Armed=False, 跳过
02:00 - Armed=True (4h宽度≥9% 且 收盘>上轨), 开始累积
      检测范围：[02:00] (1根，不够3根)
03:00 - Armed=True, 继续累积
      检测范围：[02:00, 03:00] (2根，不够3根)
04:00 - Armed=True, 继续累积
      检测范围：[02:00, 03:00, 04:00] (3根，可以检测HLH)
      合成结构：高-低-高 → HLH信号触发 ✅ 买入
05:00 - Armed=True, 继续累积
      检测范围：[02:00, 03:00, 04:00, 05:00] (4根)
06:00 - Armed=True, 继续累积
      检测范围：[02:00, 03:00, 04:00, 05:00, 06:00] (5根)
07:00 - Armed=False (宽度<9%), 重置累积
08:00 - Armed=False, 跳过
...
```

### 关键点

1. **动态累积**
   - Armed触发后，累积窗口不断扩大
   - 02:00触发 → 可以检测到08:00的数据
   - 不受4h边界限制

2. **每次验证条件1+2**
   - armed_active_4h 会自动验证宽度和上穿条件
   - 条件失效立即重置

3. **结构合并**
   - 每次累积后重新计算合成结构
   - 使用包含关系合并规则
   - 检测高-低-高(HLH)形态

## 代码关键修改

### 1. 调整计算顺序
```python
# populate_indicators 方法
# 先计算 armed_active_4h
armed_active = ...  # 状态机逻辑

# 再基于 armed_active_4h 计算 1h 结构
dataframe = self._calculate_1h_structure(dataframe)
```

### 2. 动态累积逻辑
```python
def _calculate_1h_structure(self, dataframe):
    armed_start_idx = None
    
    for i in range(len(dataframe)):
        is_armed_now = dataframe['armed_active_4h'].iloc[i]
        
        if is_armed_now:
            if armed_start_idx is None:
                armed_start_idx = i  # 记录起点
            
            # 累积从 armed_start_idx 到 i
            accumulated_slice = dataframe.iloc[armed_start_idx:i+1]
            
            if len(accumulated_slice) >= 3:
                # 检测 HLH
                result = self._process_accumulated_structure(accumulated_slice)
                if result['hlh_detected']:
                    dataframe.loc[i, 'hlh_signal'] = True
        else:
            armed_start_idx = None  # 重置
```

### 3. 累积结构处理
```python
def _process_accumulated_structure(self, accumulated_data):
    # 对累积的所有1h进行结构合并
    # 检测是否出现高-低-高形态
    # 返回 {'hlh_detected': True/False}
```

## 与截图的对应关系

| 截图要求 | 代码实现 |
|---------|---------|
| "在最新已收盘的1小时合成结构上" | ✅ 每个1h收盘后累积检测 |
| "若出现高-低-高(HLH)形态" | ✅ _process_accumulated_structure |
| "若未出现，继续向后滚动" | ✅ armed_start_idx持续累积 |
| "每次计算都要计算条件1条件2" | ✅ armed_active_4h自动验证 |

## 测试建议

### 运行回测
```bash
python -m freqtrade backtesting \
  --config user_data/config_bollinger_4h1h.json \
  --strategy Bollinger4h1hStructureStrategy \
  --timerange 20240410-20241010
```

### 查看日志
日志会显示：
- `[1h结构] Armed触发于索引 X, 时间 YYYY-MM-DD HH:00:00`
- `[1h结构] 检测到HLH信号于索引 X, 累积长度 N`
- `[1h结构] Armed失效于索引 X, 重置累积`

### 检查导出的CSV
- 文件：`user_data/debug/BollingerHLH_ETH_USDT_1h_full.csv`
- 关注列：
  - `Armed持续4h` - Armed状态
  - `HLH信号` - 是否检测到HLH
  - `入场信号` - 最终入场信号

## 注意事项

1. **预热期**
   - 默认80小时（20根4h × 4小时）
   - 确保布林带数据完整

2. **完全对齐**
   - 4h时间00:00对应1h时间00:00
   - 可能存在未来数据泄露风险
   - 仅用于验证逻辑，实盘需调整

3. **日志级别**
   - Armed触发/失效会打印日志
   - HLH检测会打印日志
   - 方便调试和验证

## 修改日期
2024-XX-XX

## 修改人
AI Assistant





