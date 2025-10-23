"""检查merge_informative_pair的对齐逻辑"""
import pandas as pd
import numpy as np
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import merge_informative_pair

print("=" * 80)
print("第二步：检查1h数据和merge对齐逻辑")
print("=" * 80)

# 读取数据
df_1h = pd.read_feather('user_data/data/binance/ETH_USDT-1h.feather')
df_4h = pd.read_feather('user_data/data/binance/ETH_USDT-4h.feather')

print(f"\n1h数据: {len(df_1h)} 行")
print(f"1h时间范围: {df_1h['date'].min()} 至 {df_1h['date'].max()}")

print(f"\n4h数据: {len(df_4h)} 行")
print(f"4h时间范围: {df_4h['date'].min()} 至 {df_4h['date'].max()}")

# 检查1h数据的前20行
print("\n" + "=" * 80)
print("1h数据的前20行")
print("=" * 80)
print(df_1h[['date', 'open', 'close']].head(20).to_string(index=False))

# 简单合并（不计算指标，只看时间对齐）
print("\n" + "=" * 80)
print("执行merge_informative_pair（简化版）")
print("=" * 80)

# 只保留必要的列进行测试
df_4h_simple = df_4h[['date', 'open', 'close']].copy()
df_4h_simple = df_4h_simple.rename(columns={'open': '4h_open_test', 'close': '4h_close_test'})

df_merged = merge_informative_pair(df_1h.copy(), df_4h_simple, '1h', '4h', ffill=True)

print(f"合并后数据: {len(df_merged)} 行")

# 查看合并后前30行（覆盖多个4h周期）
print("\n" + "=" * 80)
print("合并后的前30行（重点看时间对齐）")
print("=" * 80)

display_cols = ['date', 'close', 'date_4h', '4h_close_test_4h']
available = [c for c in display_cols if c in df_merged.columns]

for i in range(min(30, len(df_merged))):
    row = df_merged.iloc[i]
    time_1h = row['date']
    time_4h = row.get('date_4h', pd.NaT)
    close_1h = row['close']
    close_4h = row.get('4h_close_test_4h', np.nan)
    
    hour = pd.to_datetime(time_1h).hour
    marker = "★" if hour % 4 == 0 else " "
    
    print(f"{marker} {i:3d} | 1h时间: {time_1h} | 1h收盘: {close_1h:8.2f} | 4h时间: {time_4h} | 4h收盘: {close_4h}")

# 分析规律
print("\n" + "=" * 80)
print("分析对齐规律")
print("=" * 80)

# 找出第一个有4h数据的行
first_valid_4h_idx = df_merged['date_4h'].first_valid_index()
if first_valid_4h_idx is not None:
    first_row = df_merged.loc[first_valid_4h_idx]
    print(f"\n第一个有4h数据的行:")
    print(f"  索引: {first_valid_4h_idx}")
    print(f"  1h时间: {first_row['date']}")
    print(f"  4h时间: {first_row['date_4h']}")
    print(f"  1h小时: {pd.to_datetime(first_row['date']).hour}")
    
    # 检查时间差
    time_diff = pd.to_datetime(first_row['date']) - pd.to_datetime(first_row['date_4h'])
    print(f"  时间差(1h时间 - 4h时间): {time_diff}")

# 检查每个4h时间戳对应了哪些1h时间
print("\n" + "=" * 80)
print("检查4h时间戳的分布（前6个4h周期）")
print("=" * 80)

unique_4h_times = df_merged['date_4h'].dropna().unique()[:6]
for i, time_4h in enumerate(unique_4h_times):
    matched_1h = df_merged[df_merged['date_4h'] == time_4h]['date'].tolist()
    print(f"\n4h时间 {time_4h} 对应的1h时间:")
    for j, t in enumerate(matched_1h[:10]):  # 最多显示10个
        print(f"  {j+1}. {t}")
    if len(matched_1h) > 10:
        print(f"  ... 还有 {len(matched_1h) - 10} 个")

print("\n" + "=" * 80)
print("结论")
print("=" * 80)
print("\n如果1h时间03:00对应4h时间00:00，说明:")
print("  1. merge_informative_pair 可能向后偏移了3小时")
print("  2. 或者采用了'K线确认后才可用'的逻辑")
print("  3. 这是为了防止未来数据泄露（Look-Ahead Bias）")





