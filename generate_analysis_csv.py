"""生成详细的策略分析CSV"""
import sys
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import merge_informative_pair

print("=" * 80)
print("生成策略分析CSV")
print("=" * 80)

# 策略参数（直接使用默认值）
bb_period = 20
bb_stdev = 2.0
width_threshold = 0.09

print(f"\n策略参数:")
print(f"  width_threshold = {width_threshold} ({width_threshold*100}%)")
print(f"  bb_period = {bb_period}")
print(f"  bb_stdev = {bb_stdev}")

# 读取数据
df_1h = pd.read_feather('user_data/data/binance/ETH_USDT-1h.feather')
df_4h = pd.read_feather('user_data/data/binance/ETH_USDT-4h.feather')

print(f"\n数据范围:")
print(f"  1h: {len(df_1h)} 行, {df_1h['date'].min()} ~ {df_1h['date'].max()}")
print(f"  4h: {len(df_4h)} 行, {df_4h['date'].min()} ~ {df_4h['date'].max()}")

# 处理数据
metadata = {'pair': 'ETH/USDT'}

# 先处理4h数据
df_4h_processed = strategy.populate_indicators_4h(df_4h.copy(), metadata)

# 使用merge合并
from freqtrade.strategy import merge_informative_pair
df_merged = merge_informative_pair(
    df_1h.copy(),
    df_4h_processed,
    '1h',
    '4h',
    ffill=True
)

# 手动执行populate_indicators的关键部分
# 兜底计算
if 'bb_width_4h' not in df_merged.columns:
    if all(c in df_merged.columns for c in ['bb_upper_4h', 'bb_lower_4h', 'bb_middle_4h']):
        df_merged['bb_width_4h'] = (
            (df_merged['bb_upper_4h'] - df_merged['bb_lower_4h']) / df_merged['bb_middle_4h']
        )

if 'is_width_ok_4h' not in df_merged.columns:
    if 'bb_width_4h' in df_merged.columns:
        df_merged['is_width_ok_4h'] = df_merged['bb_width_4h'] >= strategy.width_threshold.value
    else:
        df_merged['is_width_ok_4h'] = False

if 'is_breakout_4h' not in df_merged.columns:
    if all(c in df_merged.columns for c in ['close_4h', 'bb_upper_4h']):
        df_merged['is_breakout_4h'] = df_merged['close_4h'] > df_merged['bb_upper_4h']
    else:
        df_merged['is_breakout_4h'] = False

if 'is_below_lower_4h' not in df_merged.columns:
    if all(c in df_merged.columns for c in ['close_4h', 'bb_lower_4h']):
        df_merged['is_below_lower_4h'] = df_merged['close_4h'] <= df_merged['bb_lower_4h']
    else:
        df_merged['is_below_lower_4h'] = False

if 'is_armed_4h' not in df_merged.columns:
    df_merged['is_armed_4h'] = df_merged['is_width_ok_4h'] & df_merged['is_breakout_4h']

# 计算1h结构
df_merged = strategy._calculate_1h_structure(df_merged)

# 计算armed_active_4h（粘性状态）
if 'is_armed_4h' in df_merged.columns:
    armed_active = pd.Series(False, index=df_merged.index)
    current_state = False
    
    for i in range(len(df_merged)):
        is_armed = bool(df_merged['is_armed_4h'].iloc[i]) if pd.notna(df_merged['is_armed_4h'].iloc[i]) else False
        is_below = bool(df_merged['is_below_lower_4h'].iloc[i]) if 'is_below_lower_4h' in df_merged.columns and pd.notna(df_merged['is_below_lower_4h'].iloc[i]) else False
        is_width = bool(df_merged['is_width_ok_4h'].iloc[i]) if 'is_width_ok_4h' in df_merged.columns and pd.notna(df_merged['is_width_ok_4h'].iloc[i]) else True
        
        if is_armed:
            current_state = True
        elif is_below or not is_width:
            current_state = False
        
        armed_active.iloc[i] = current_state
    
    df_merged['armed_active_4h'] = armed_active
else:
    df_merged['armed_active_4h'] = False

# 计算入场信号
df_merged['entry_signal'] = df_merged['armed_active_4h'] & df_merged['hlh_signal']

print(f"\n处理结果:")
print(f"  Armed状态(is_armed_4h): {df_merged['is_armed_4h'].sum()} 次")
print(f"  Armed持续(armed_active_4h): {df_merged['armed_active_4h'].sum()} 次")
print(f"  HLH信号: {df_merged['hlh_signal'].sum()} 次")
print(f"  入场信号: {df_merged['entry_signal'].sum()} 次")

# 准备输出CSV
output_cols = [
    'date',
    'open', 'high', 'low', 'close', 'volume',
    'date_4h', 'close_4h', 
    'bb_upper_4h', 'bb_middle_4h', 'bb_lower_4h', 'bb_width_4h',
    'is_width_ok_4h', 'is_breakout_4h', 'is_below_lower_4h',
    'is_armed_4h', 'armed_active_4h',
    'structure_high', 'structure_low', 'structure_type', 'hlh_signal',
    'entry_signal'
]

# 确保所有列存在
for col in output_cols:
    if col not in df_merged.columns:
        df_merged[col] = np.nan

# 创建输出数据
output_df = df_merged[output_cols].copy()

# 添加一些辅助列用于分析
output_df['bb_width_pct'] = (output_df['bb_width_4h'] * 100).round(2)  # 百分比
output_df['close_vs_upper'] = (output_df['close_4h'] - output_df['bb_upper_4h']).round(2)  # 价格vs上轨差值
output_df['armed_active_changed'] = output_df['armed_active_4h'] != output_df['armed_active_4h'].shift()

# 导出完整数据
output_file = 'strategy_analysis_full.csv'
output_df.to_csv(output_file, index=False, encoding='utf-8-sig')
print(f"\n✅ 完整CSV已导出: {output_file}")

# 导出只包含Armed时段的数据
armed_periods = output_df[output_df['armed_active_4h']].copy()
if len(armed_periods) > 0:
    armed_file = 'strategy_analysis_armed_only.csv'
    armed_periods.to_csv(armed_file, index=False, encoding='utf-8-sig')
    print(f"✅ Armed时段CSV已导出: {armed_file} ({len(armed_periods)} 行)")
    
    # 显示Armed时段的统计
    print(f"\nArmed时段统计:")
    print(f"  总时长: {len(armed_periods)} 小时")
    print(f"  HLH信号出现: {armed_periods['hlh_signal'].sum()} 次")
    print(f"  入场信号: {armed_periods['entry_signal'].sum()} 次")
    
    if armed_periods['entry_signal'].sum() > 0:
        print(f"\n✨ 入场时间点:")
        entry_times = armed_periods[armed_periods['entry_signal']]['date'].tolist()
        for t in entry_times[:10]:
            print(f"  - {t}")
else:
    print(f"\n⚠️ 没有Armed时段！")

# 导出关键事件
events = []

# Armed开始和结束
for i in range(1, len(output_df)):
    if output_df['armed_active_4h'].iloc[i] and not output_df['armed_active_4h'].iloc[i-1]:
        events.append({
            'time': output_df['date'].iloc[i],
            'event': 'Armed开始',
            'close': output_df['close'].iloc[i],
            'bb_width': output_df['bb_width_pct'].iloc[i],
            'hlh': output_df['hlh_signal'].iloc[i]
        })
    elif not output_df['armed_active_4h'].iloc[i] and output_df['armed_active_4h'].iloc[i-1]:
        events.append({
            'time': output_df['date'].iloc[i],
            'event': 'Armed结束',
            'close': output_df['close'].iloc[i],
            'bb_width': output_df['bb_width_pct'].iloc[i],
            'hlh': output_df['hlh_signal'].iloc[i]
        })

# HLH信号
hlh_signals = output_df[output_df['hlh_signal']]
for idx, row in hlh_signals.iterrows():
    events.append({
        'time': row['date'],
        'event': 'HLH信号',
        'close': row['close'],
        'bb_width': row['bb_width_pct'],
        'armed': row['armed_active_4h']
    })

events_df = pd.DataFrame(events).sort_values('time')
events_file = 'strategy_analysis_events.csv'
events_df.to_csv(events_file, index=False, encoding='utf-8-sig')
print(f"✅ 事件记录CSV已导出: {events_file} ({len(events_df)} 个事件)")

print(f"\n" + "=" * 80)
print("分析完成！")
print("=" * 80)
print(f"\n生成的文件:")
print(f"  1. {output_file} - 完整数据")
print(f"  2. {armed_file if len(armed_periods) > 0 else '(无Armed时段)'} - Armed时段数据")
print(f"  3. {events_file} - 关键事件")

