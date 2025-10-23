"""导出1h+4h合并数据（完全对齐版本 - 00:00对00:00）"""
import pandas as pd
import numpy as np
import freqtrade.vendor.qtpylib.indicators as qtpylib

print("=" * 80)
print("导出1h+4h合并数据（完全对齐版本）")
print("=" * 80)

# 策略参数
bb_period = 20
bb_stdev = 2.0
width_threshold = 0.09

# 读取数据
print("\n读取数据...")
df_1h = pd.read_feather('user_data/data/binance/ETH_USDT-1h.feather')
df_4h = pd.read_feather('user_data/data/binance/ETH_USDT-4h.feather')

print(f"1h数据: {len(df_1h)} 行")
print(f"4h数据: {len(df_4h)} 行")

# 处理4h数据 - 计算布林带
print("\n计算4h布林带...")
bollinger_4h = qtpylib.bollinger_bands(df_4h['close'], window=bb_period, stds=bb_stdev)
df_4h['bb_upper'] = bollinger_4h['upper']
df_4h['bb_middle'] = bollinger_4h['mid']
df_4h['bb_lower'] = bollinger_4h['lower']
df_4h['bb_width'] = (df_4h['bb_upper'] - df_4h['bb_lower']) / df_4h['bb_middle']

# 4h条件
df_4h['is_width_ok'] = df_4h['bb_width'] >= width_threshold
df_4h['is_breakout'] = df_4h['close'] > df_4h['bb_upper']
df_4h['is_below_lower'] = df_4h['close'] <= df_4h['bb_lower']
df_4h['is_armed'] = df_4h['is_width_ok'] & df_4h['is_breakout']

# 手动合并：为1h数据添加"所属4h时间"列
print("\n手动合并（完全对齐）...")

# 计算每个1h时间对应的4h时间（向下取整到4h边界）
df_1h['date_4h_aligned'] = df_1h['date'].dt.floor('4H')

# 重命名4h列以便合并
df_4h_renamed = df_4h.rename(columns={
    'date': 'date_4h_aligned',
    'open': 'open_4h',
    'high': 'high_4h',
    'low': 'low_4h',
    'close': 'close_4h',
    'volume': 'volume_4h',
    'bb_upper': 'bb_upper_4h',
    'bb_middle': 'bb_middle_4h',
    'bb_lower': 'bb_lower_4h',
    'bb_width': 'bb_width_4h',
    'is_width_ok': 'is_width_ok_4h',
    'is_breakout': 'is_breakout_4h',
    'is_below_lower': 'is_below_lower_4h',
    'is_armed': 'is_armed_4h',
})

# 使用left join合并
df_merged = df_1h.merge(df_4h_renamed, on='date_4h_aligned', how='left')

# 重命名回来
df_merged = df_merged.rename(columns={'date_4h_aligned': 'date_4h'})

print(f"合并后数据: {len(df_merged)} 行")

# 添加4小时更新标记
print("\n添加4小时更新标记...")
df_merged['4h_update_flag'] = ''
for idx, row in df_merged.iterrows():
    hour = pd.to_datetime(row['date']).hour
    if hour % 4 == 0:
        df_merged.loc[idx, '4h_update_flag'] = '★'

# 重命名为中文列名
print("转换为中文列名...")
column_mapping = {
    'date': '时间',
    'open': '开盘价',
    'high': '最高价',
    'low': '最低价',
    'close': '收盘价',
    'volume': '成交量',
    'date_4h': '4h时间',
    'open_4h': '4h开盘价',
    'high_4h': '4h最高价',
    'low_4h': '4h最低价',
    'close_4h': '4h收盘价',
    'volume_4h': '4h成交量',
    'bb_upper_4h': '4h布林上轨',
    'bb_middle_4h': '4h布林中轨',
    'bb_lower_4h': '4h布林下轨',
    'bb_width_4h': '4h布林宽度',
    'is_width_ok_4h': '4h宽度达标',
    'is_breakout_4h': '4h上穿上轨',
    'is_below_lower_4h': '4h跌破下轨',
    'is_armed_4h': '4h_Armed',
    '4h_update_flag': '4小时更新标记',
}

df_export = df_merged.rename(columns={k: v for k, v in column_mapping.items() if k in df_merged.columns})

# 调整列顺序：把"4小时更新标记"放在"时间"列右侧
print("调整列顺序...")
cols = df_export.columns.tolist()
if '4小时更新标记' in cols and '时间' in cols:
    cols.remove('4小时更新标记')
    time_index = cols.index('时间')
    cols.insert(time_index + 1, '4小时更新标记')
    df_export = df_export[cols]

# 导出CSV
print("\n导出CSV...")
csv_file = 'merged_1h_4h_data_aligned.csv'
df_export.to_csv(csv_file, index=False, encoding='utf-8-sig')

print(f"\n✅ CSV文件已生成: {csv_file}")
print(f"   总行数: {len(df_export)}")
print(f"   总列数: {len(df_export.columns)}")

# 验证对齐
print("\n" + "=" * 80)
print("验证对齐情况（前20行）")
print("=" * 80)
key_cols = ['时间', '4小时更新标记', '4h时间', '收盘价', '4h收盘价', '4h布林上轨', '4h宽度达标', '4h_Armed']
available_cols = [col for col in key_cols if col in df_export.columns]
print(df_export[available_cols].head(20).to_string(index=False))

# 统计信息
print("\n" + "=" * 80)
print("统计信息")
print("=" * 80)

if '4h宽度达标' in df_export.columns:
    width_ok_count = df_export['4h宽度达标'].sum()
    print(f"宽度≥9%: {width_ok_count} 小时 ({width_ok_count/len(df_export)*100:.1f}%)")

if '4h上穿上轨' in df_export.columns:
    breakout_count = df_export['4h上穿上轨'].sum()
    print(f"上穿上轨: {breakout_count} 小时 ({breakout_count/len(df_export)*100:.1f}%)")

if '4h_Armed' in df_export.columns:
    armed_count = df_export['4h_Armed'].sum()
    print(f"Armed状态: {armed_count} 小时 ({armed_count/len(df_export)*100:.1f}%)")

print("\n" + "=" * 80)
print("✅ 完成！现在4h时间 00:00 对齐 1h时间 00:00")
print("=" * 80)
print("\n⚠️  注意：这种对齐方式在实盘中会造成未来数据泄露！")
print("   - 在00:00时，你看到的是00:00-04:00整根K线的最终收盘价")
print("   - 但实际上这根K线要到04:00才收盘")
print("   - 仅用于数据分析，不适合回测或实盘！")





