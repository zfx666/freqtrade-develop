"""测试策略完整流程"""
import sys
sys.path.insert(0, '.')

import pandas as pd
from user_data.strategies.Bollinger4h1hStructureStrategy import Bollinger4h1hStructureStrategy
from freqtrade.configuration import Configuration

# 加载配置
config = Configuration.from_files(['user_data/config_bollinger_4h1h.json'])

# 创建策略实例
strategy = Bollinger4h1hStructureStrategy(config['original_config'])

print("=" * 80)
print("策略参数检查")
print("=" * 80)
print(f"width_threshold.value = {strategy.width_threshold.value}")
print(f"bb_period.value = {strategy.bb_period.value}")
print(f"bb_stdev.value = {strategy.bb_stdev.value}")

# 读取数据
df_1h = pd.read_feather('user_data/data/binance/BTC_USDT-1h.feather')
df_4h = pd.read_feather('user_data/data/binance/BTC_USDT-4h.feather')

print("\n" + "=" * 80)
print("数据加载")
print("=" * 80)
print(f"1h数据: {len(df_1h)} 行")
print(f"4h数据: {len(df_4h)} 行")

# 模拟策略的populate_indicators_4h
metadata = {'pair': 'BTC/USDT'}
df_4h_processed = strategy.populate_indicators_4h(df_4h.copy(), metadata)

print("\n" + "=" * 80)
print("4h指标计算结果")
print("=" * 80)
print(f"df_4h_processed列: {df_4h_processed.columns.tolist()}")

if 'is_armed' in df_4h_processed.columns:
    armed_count_4h = df_4h_processed['is_armed'].sum()
    print(f"4h Armed次数: {armed_count_4h}")
    
    if armed_count_4h > 0:
        armed_rows = df_4h_processed[df_4h_processed['is_armed']]['date'].head(5)
        print(f"前5个Armed时间:")
        for t in armed_rows:
            print(f"  {t}")

# 测试合并后的效果
print("\n" + "=" * 80)
print("测试1h指标计算（包括合并4h）")
print("=" * 80)

# 这里不能直接调用populate_indicators，因为它需要DataProvider
# 但我们可以看看兜底逻辑
from freqtrade.strategy import merge_informative_pair

df_merged = merge_informative_pair(
    df_1h.copy(),
    df_4h_processed,
    '1h',
    '4h',
    ffill=True
)

print(f"合并后数据: {len(df_merged)} 行")
print(f"合并后的4h相关列:")
for col in sorted(df_merged.columns):
    if '4h' in col:
        non_null = df_merged[col].notna().sum()
        if df_merged[col].dtype == bool or col.startswith('is_'):
            true_count = df_merged[col].sum() if df_merged[col].dtype == bool else (df_merged[col] == True).sum()
            print(f"  {col}: {true_count} 为True (共{non_null}非空)")
        else:
            print(f"  {col}: {non_null} 非空")

# 检查兜底逻辑是否会被触发
print("\n" + "=" * 80)
print("检查兜底逻辑")
print("=" * 80)
print(f"'is_armed_4h' in columns: {'is_armed_4h' in df_merged.columns}")
print(f"'bb_width_4h' in columns: {'bb_width_4h' in df_merged.columns}")
print(f"'is_width_ok_4h' in columns: {'is_width_ok_4h' in df_merged.columns}")

if 'bb_width_4h' in df_merged.columns:
    # 模拟兜底计算
    test_threshold = strategy.width_threshold.value
    print(f"\n使用阈值 {test_threshold} 重新计算:")
    test_is_width_ok = df_merged['bb_width_4h'] >= test_threshold
    print(f"  宽度达标次数: {test_is_width_ok.sum()}")

