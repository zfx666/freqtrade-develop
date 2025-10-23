"""导出1h+4h合并数据（原始版本）"""
import pandas as pd
import numpy as np
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import merge_informative_pair

print("=" * 80)
print("导出1h+4h合并数据")
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

# 合并数据
print("合并1h和4h数据...")
df_merged = merge_informative_pair(df_1h.copy(), df_4h, '1h', '4h', ffill=True)

print(f"合并后数据: {len(df_merged)} 行")

# 添加4小时更新标记
print("\n添加4小时更新标记...")
df_merged['4h_update_flag'] = ''
for idx, row in df_merged.iterrows():
    hour = pd.to_datetime(row['date']).hour
    # 4h K线在 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 开始
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

# 只重命名存在的列
df_export = df_merged.rename(columns={k: v for k, v in column_mapping.items() if k in df_merged.columns})

# 调整列顺序：把"4小时更新标记"放在"时间"列右侧
print("调整列顺序...")
cols = df_export.columns.tolist()
if '4小时更新标记' in cols and '时间' in cols:
    cols.remove('4小时更新标记')
    time_index = cols.index('时间')
    cols.insert(time_index + 1, '4小时更新标记')
    df_export = df_export[cols]

# 导出
print("\n导出CSV...")
csv_file = 'merged_1h_4h_data.csv'
df_export.to_csv(csv_file, index=False, encoding='utf-8-sig')

print(f"\n✅ CSV文件已生成: {csv_file}")
print(f"   总行数: {len(df_export)}")
print(f"   总列数: {len(df_export.columns)}")

# 显示前10行
print("\n" + "=" * 80)
print("前10行数据预览")
print("=" * 80)
key_cols = ['时间', '4小时更新标记', '收盘价', '4h时间', '4h收盘价', '4h布林上轨', '4h布林宽度', '4h_Armed']
available_cols = [col for col in key_cols if col in df_export.columns]
print(df_export[available_cols].head(10).to_string(index=False))

print("\n" + "=" * 80)
print("完成！")
print("=" * 80)
