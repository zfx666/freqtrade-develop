import pandas as pd
import numpy as np

# 检查4h数据
print("=" * 60)
print("检查 BTC/USDT 4h 数据")
print("=" * 60)
df_4h = pd.read_feather('user_data/data/binance/BTC_USDT-4h.feather')
print(f"4h数据总行数: {len(df_4h)}")
print(f"开始时间: {df_4h['date'].min()}")
print(f"结束时间: {df_4h['date'].max()}")
print(f"\n最新10行数据:")
print(df_4h.tail(10)[['date', 'open', 'high', 'low', 'close', 'volume']])

# 检查1h数据
print("\n" + "=" * 60)
print("检查 BTC/USDT 1h 数据")
print("=" * 60)
df_1h = pd.read_feather('user_data/data/binance/BTC_USDT-1h.feather')
print(f"1h数据总行数: {len(df_1h)}")
print(f"开始时间: {df_1h['date'].min()}")
print(f"结束时间: {df_1h['date'].max()}")
print(f"\n最新10行数据:")
print(df_1h.tail(10)[['date', 'open', 'high', 'low', 'close', 'volume']])

# 计算布林带宽度（模拟策略计算）
print("\n" + "=" * 60)
print("计算4h布林带宽度（最近10根K线）")
print("=" * 60)

from freqtrade.vendor.qtpylib import indicators as qtpylib

bb_period = 20
bb_stdev = 2.0

bollinger = qtpylib.bollinger_bands(
    df_4h['close'],
    window=bb_period,
    stds=bb_stdev
)
df_4h['bb_upper'] = bollinger['upper']
df_4h['bb_middle'] = bollinger['mid']
df_4h['bb_lower'] = bollinger['lower']
df_4h['bb_width'] = (df_4h['bb_upper'] - df_4h['bb_lower']) / df_4h['bb_middle']

# 检查宽度阈值
width_threshold = 0.0001  # 配置中的默认值
df_4h['is_width_ok'] = df_4h['bb_width'] >= width_threshold
df_4h['is_breakout'] = df_4h['close'] > df_4h['bb_upper']

print("\n最近10根4h K线的布林带分析:")
cols = ['date', 'close', 'bb_upper', 'bb_middle', 'bb_lower', 'bb_width', 'is_width_ok', 'is_breakout']
print(df_4h.tail(10)[cols].to_string(index=False))

print(f"\n宽度阈值设置: {width_threshold} ({width_threshold*100}%)")
print(f"宽度达标次数: {df_4h['is_width_ok'].sum()}")
print(f"上穿上轨次数: {df_4h['is_breakout'].sum()}")
print(f"Armed状态次数（宽度达标且上穿上轨）: {(df_4h['is_width_ok'] & df_4h['is_breakout']).sum()}")

# 显示回测时间范围内的数据
print("\n" + "=" * 60)
print("回测时间范围 20240410-20241010 的数据统计")
print("=" * 60)
df_4h['date'] = pd.to_datetime(df_4h['date'])
backtest_data = df_4h[(df_4h['date'] >= '2024-04-10') & (df_4h['date'] <= '2024-10-10')]
print(f"回测范围内4h数据行数: {len(backtest_data)}")
if len(backtest_data) > 0:
    print(f"回测范围开始: {backtest_data['date'].min()}")
    print(f"回测范围结束: {backtest_data['date'].max()}")
    print(f"回测范围内宽度达标次数: {backtest_data['is_width_ok'].sum()}")
    print(f"回测范围内上穿上轨次数: {backtest_data['is_breakout'].sum()}")
    print(f"回测范围内Armed状态次数: {(backtest_data['is_width_ok'] & backtest_data['is_breakout']).sum()}")
else:
    print("警告: 回测时间范围内没有数据！")


