"""检查原始4h数据的时间戳"""
import pandas as pd

print("=" * 80)
print("检查原始4h数据")
print("=" * 80)

# 读取4h数据
df_4h = pd.read_feather('user_data/data/binance/ETH_USDT-4h.feather')

print(f"\n4h数据总行数: {len(df_4h)}")
print(f"时间范围: {df_4h['date'].min()} 至 {df_4h['date'].max()}")

print("\n前20行4h数据:")
print(df_4h[['date', 'open', 'high', 'low', 'close', 'volume']].head(20).to_string(index=False))

print("\n" + "=" * 80)
print("检查时间间隔（前10个间隔）")
print("=" * 80)

# 计算时间差
df_4h['time_diff'] = df_4h['date'].diff()

print("\n时间戳 -> 下一个时间戳的间隔:")
for i in range(1, min(11, len(df_4h))):
    print(f"{df_4h['date'].iloc[i-1]} -> {df_4h['date'].iloc[i]} = {df_4h['time_diff'].iloc[i]}")

print("\n" + "=" * 80)
print("检查特定日期的4h时间戳")
print("=" * 80)

# 筛选2024-10-10附近的数据（需要加上时区）
target_date = pd.to_datetime('2024-10-10', utc=True)
df_around = df_4h[(df_4h['date'] >= target_date - pd.Timedelta(days=1)) & 
                   (df_4h['date'] <= target_date + pd.Timedelta(days=1))]

print(f"\n2024-10-09到2024-10-11的4h数据:")
print(df_around[['date', 'open', 'close']].to_string(index=False))

print("\n" + "=" * 80)
print("分析结论")
print("=" * 80)

# 检查是否所有间隔都是4小时
all_diffs = df_4h['time_diff'].dropna()
is_uniform = (all_diffs == pd.Timedelta(hours=4)).all()

print(f"\n所有时间间隔是否都是4小时: {is_uniform}")
if not is_uniform:
    print("发现非4小时间隔:")
    non_4h = df_4h[df_4h['time_diff'] != pd.Timedelta(hours=4)]
    print(non_4h[['date', 'time_diff']].head(10))

# 检查时间戳的小时值
hours = df_4h['date'].dt.hour.unique()
print(f"\n4h数据的小时值分布: {sorted(hours)}")
print(f"预期应该是: [0, 4, 8, 12, 16, 20]")

if list(sorted(hours)) == [0, 4, 8, 12, 16, 20]:
    print("✅ 时间戳符合预期，是K线开盘时间")
else:
    print("⚠️  时间戳不符合预期")

