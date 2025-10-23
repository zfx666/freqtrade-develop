"""生成ETH/USDT策略分析CSV"""
import pandas as pd
import numpy as np
import freqtrade.vendor.qtpylib.indicators as qtpylib

print("=" * 80)
print("生成ETH/USDT策略分析CSV")
print("=" * 80)

# 策略参数
bb_period = 20
bb_stdev = 2.0
width_threshold = 0.09

print(f"\n策略参数:")
print(f"  width_threshold = {width_threshold} ({width_threshold*100}%)")
print(f"  bb_period = {bb_period}")
print(f"  bb_stdev = {bb_stdev}")

# 读取数据
print("\n读取数据...")
df_1h = pd.read_feather('user_data/data/binance/ETH_USDT-1h.feather')
df_4h = pd.read_feather('user_data/data/binance/ETH_USDT-4h.feather')

print(f"  1h: {len(df_1h)} 行, {df_1h['date'].min()} ~ {df_1h['date'].max()}")
print(f"  4h: {len(df_4h)} 行, {df_4h['date'].min()} ~ {df_4h['date'].max()}")

# 处理4h数据
print("\n计算4h指标...")
bollinger_4h = qtpylib.bollinger_bands(df_4h['close'], window=bb_period, stds=bb_stdev)
df_4h['bb_upper'] = bollinger_4h['upper']
df_4h['bb_middle'] = bollinger_4h['mid']
df_4h['bb_lower'] = bollinger_4h['lower']
df_4h['bb_width'] = (df_4h['bb_upper'] - df_4h['bb_lower']) / df_4h['bb_middle']

df_4h['is_width_ok'] = df_4h['bb_width'] >= width_threshold
df_4h['is_breakout'] = df_4h['close'] > df_4h['bb_upper']
df_4h['is_below_lower'] = df_4h['close'] <= df_4h['bb_lower']
df_4h['is_armed'] = df_4h['is_width_ok'] & df_4h['is_breakout']

# 合并数据
print("合并1h和4h数据...")
from freqtrade.strategy import merge_informative_pair
df_merged = merge_informative_pair(df_1h.copy(), df_4h, '1h', '4h', ffill=True)

# 计算armed_active_4h（粘性状态）
print("计算Armed粘性状态...")
armed_active = pd.Series(False, index=df_merged.index)
current_state = False

for i in range(len(df_merged)):
    is_armed = bool(df_merged['is_armed_4h'].iloc[i]) if pd.notna(df_merged['is_armed_4h'].iloc[i]) else False
    is_below = bool(df_merged['is_below_lower_4h'].iloc[i]) if pd.notna(df_merged['is_below_lower_4h'].iloc[i]) else False
    is_width = bool(df_merged['is_width_ok_4h'].iloc[i]) if pd.notna(df_merged['is_width_ok_4h'].iloc[i]) else True
    
    if is_armed:
        current_state = True
    elif is_below or not is_width:
        current_state = False
    
    armed_active.iloc[i] = current_state

df_merged['armed_active_4h'] = armed_active

# 简化的HLH检测（基于价格形态）
print("计算HLH信号...")
df_merged['hlh_signal'] = False

# 每4根1h K线为一组，检测HLH模式
for i in range(3, len(df_merged)):
    # 简单的高低高检测：price[i-2] > price[i-1] < price[i]
    if i >= 2:
        h1 = df_merged['high'].iloc[i-2]
        l = df_merged['low'].iloc[i-1]
        h2 = df_merged['high'].iloc[i]
        
        # HLH: 高点-低点-高点
        if h1 > l and l < h2:
            df_merged.loc[df_merged.index[i], 'hlh_signal'] = True

# 计算入场信号
df_merged['entry_signal'] = df_merged['armed_active_4h'] & df_merged['hlh_signal']

print(f"\n处理结果:")
print(f"  Armed状态(is_armed_4h): {df_merged['is_armed_4h'].sum()} 次")
print(f"  Armed持续(armed_active_4h): {df_merged['armed_active_4h'].sum()} 次")
print(f"  HLH信号: {df_merged['hlh_signal'].sum()} 次")
print(f"  入场信号: {df_merged['entry_signal'].sum()} 次")

# 准备输出
print("\n导出CSV...")
df_merged['bb_width_pct'] = (df_merged['bb_width_4h'] * 100).round(2)
df_merged['close_vs_upper'] = (df_merged['close_4h'] - df_merged['bb_upper_4h']).round(2)

# 输出列
output_cols = [
    'date', 'open', 'high', 'low', 'close', 'volume',
    'date_4h', 'close_4h', 
    'bb_upper_4h', 'bb_middle_4h', 'bb_lower_4h', 
    'bb_width_4h', 'bb_width_pct',
    'is_width_ok_4h', 'is_breakout_4h', 'is_below_lower_4h',
    'is_armed_4h', 'armed_active_4h',
    'hlh_signal', 'entry_signal', 'close_vs_upper'
]

# 确保所有列存在
for col in output_cols:
    if col not in df_merged.columns:
        df_merged[col] = np.nan

output_df = df_merged[output_cols].copy()

# 导出完整数据
full_file = 'eth_analysis_full.csv'
output_df.to_csv(full_file, index=False, encoding='utf-8-sig')
print(f"✅ 完整数据: {full_file} ({len(output_df)} 行)")

# 导出Armed时段
armed_df = output_df[output_df['armed_active_4h']].copy()
if len(armed_df) > 0:
    armed_file = 'eth_analysis_armed.csv'
    armed_df.to_csv(armed_file, index=False, encoding='utf-8-sig')
    print(f"✅ Armed时段: {armed_file} ({len(armed_df)} 行)")
    print(f"   - HLH信号: {armed_df['hlh_signal'].sum()} 次")
    print(f"   - 入场信号: {armed_df['entry_signal'].sum()} 次")
    
    if armed_df['entry_signal'].sum() > 0:
        entry_df = armed_df[armed_df['entry_signal']]
        entry_file = 'eth_analysis_entries.csv'
        entry_df.to_csv(entry_file, index=False, encoding='utf-8-sig')
        print(f"✅ 入场信号: {entry_file}")
        print("\n入场时间:")
        for idx, row in entry_df.iterrows():
            print(f"  {row['date']}: 价格={row['close']:.2f}, 宽度={row['bb_width_pct']:.2f}%")
else:
    print("⚠️  没有Armed时段")

print("\n" + "=" * 80)
print("完成！")





