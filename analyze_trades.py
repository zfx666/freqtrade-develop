"""分析回测交易明细，带策略指标"""
import pandas as pd
import numpy as np
import json
import glob
from pathlib import Path

print("=" * 80)
print("交易明细分析")
print("=" * 80)

# 1. 找到最新的回测结果文件
backtest_dir = Path('user_data/backtest_results')
result_files = list(backtest_dir.glob('*.json'))

if not result_files:
    print("❌ 未找到回测结果文件！请先运行回测。")
    exit(1)

# 按修改时间排序，获取最新的
latest_result = max(result_files, key=lambda p: p.stat().st_mtime)
print(f"\n使用回测结果: {latest_result.name}")

# 2. 读取回测结果
with open(latest_result, 'r', encoding='utf-8') as f:
    backtest_data = json.load(f)

# 调试：打印JSON结构
print(f"\nJSON keys: {backtest_data.keys()}")

# 尝试不同的JSON结构
if 'strategy' in backtest_data:
    strategy_name = list(backtest_data['strategy'].keys())[0]
    trades = backtest_data['strategy'][strategy_name]['trades']
elif 'backtest_result' in backtest_data:
    # 新版本格式
    trades = backtest_data['backtest_result'].get('trades', [])
    strategy_name = backtest_data.get('strategy_name', 'Unknown')
else:
    # 直接查找trades
    trades = backtest_data.get('trades', [])
    strategy_name = backtest_data.get('strategy', 'Unknown')

print(f"策略: {strategy_name}")
print(f"交易数量: {len(trades)}")

if len(trades) == 0:
    print("\n❌ 没有交易记录！")
    
    # 读取策略生成的调试CSV
    debug_csv = Path('user_data/debug')
    csv_files = list(debug_csv.glob('*_full.csv'))
    if csv_files:
        print("\n尝试分析策略调试CSV...")
        df = pd.read_csv(csv_files[0], encoding='utf-8-sig')
        
        print(f"\n数据行数: {len(df)}")
        print(f"列: {df.columns.tolist()}")
        
        # 分析为何没有交易
        if 'Armed持续4h' in df.columns:
            armed_count = (df['Armed持续4h'] == True).sum()
            print(f"\nArmed持续4h次数: {armed_count}")
        
        if 'HLH信号' in df.columns:
            hlh_count = (df['HLH信号'] == True).sum()
            print(f"HLH信号次数: {hlh_count}")
        
        if 'Armed持续4h' in df.columns and 'HLH信号' in df.columns:
            entry_count = ((df['Armed持续4h'] == True) & (df['HLH信号'] == True)).sum()
            print(f"理论入场信号: {entry_count}")
            
            if entry_count > 0:
                entry_df = df[(df['Armed持续4h'] == True) & (df['HLH信号'] == True)]
                print(f"\n入场信号时间点:")
                for idx, row in entry_df.head(10).iterrows():
                    print(f"  {row['时间']}: 价格={row['收盘价']:.2f}, 宽度={row.get('布林宽度4h', 0)*100:.2f}%")
        
        # 导出无交易分析
        analysis_file = 'no_trades_analysis.csv'
        df.to_csv(analysis_file, index=False, encoding='utf-8-sig')
        print(f"\n✅ 详细数据已导出: {analysis_file}")
    
    exit(0)

# 3. 转换为DataFrame
trades_df = pd.DataFrame(trades)

# 尝试获取总盈亏（兼容不同版本）
try:
    if 'strategy' in backtest_data:
        profit_abs = backtest_data['strategy'][strategy_name]['pairlist'][0]['profit_abs']
        wins = backtest_data['strategy'][strategy_name]['results_per_pair'][0]['wins']
    else:
        profit_abs = sum([t.get('profit_abs', 0) for t in trades])
        wins = len([t for t in trades if t.get('profit_ratio', 0) > 0])
    
    print(f"\n总盈亏: {profit_abs:.2f} USDT")
    print(f"胜率: {wins}/{len(trades)}")
except:
    print(f"\n交易笔数: {len(trades)}")

# 4. 读取1h数据和策略指标
print("\n加载策略指标数据...")

# 读取策略导出的CSV（包含所有指标）
debug_dir = Path('user_data/debug')
csv_files = list(debug_dir.glob('*ETH_USDT*_full.csv'))

if csv_files:
    indicators_df = pd.read_csv(csv_files[0], encoding='utf-8-sig')
    print(f"指标数据: {len(indicators_df)} 行")
    
    # 转换时间列
    if '时间' in indicators_df.columns:
        indicators_df['时间'] = pd.to_datetime(indicators_df['时间'])
    elif 'date' in indicators_df.columns:
        indicators_df['date'] = pd.to_datetime(indicators_df['date'])
        indicators_df['时间'] = indicators_df['date']
else:
    print("⚠️ 未找到策略指标CSV，将使用原始数据")
    indicators_df = None

# 5. 构建详细交易分析
trade_analysis = []

for idx, trade in trades_df.iterrows():
    open_time = pd.to_datetime(trade['open_date'])
    close_time = pd.to_datetime(trade['close_date'])
    
    analysis = {
        '交易序号': idx + 1,
        '交易对': trade['pair'],
        '开仓时间': open_time,
        '平仓时间': close_time,
        '持仓时长(小时)': (close_time - open_time).total_seconds() / 3600,
        '开仓价格': trade['open_rate'],
        '平仓价格': trade['close_rate'],
        '止损价': trade.get('stop_loss_abs', 0),
        '盈亏%': trade['profit_ratio'] * 100,
        '盈亏金额': trade['profit_abs'],
        '平仓原因': trade.get('exit_reason', 'unknown'),
        '入场标签': trade.get('enter_tag', ''),
        '出场标签': trade.get('exit_tag', ''),
    }
    
    # 添加开仓时的指标
    if indicators_df is not None:
        # 找到开仓时间最接近的那一行
        time_diff = abs(indicators_df['时间'] - open_time)
        open_idx = time_diff.idxmin()
        open_row = indicators_df.loc[open_idx]
        
        analysis.update({
            '开仓_4h宽度%': open_row.get('布林宽度4h', 0) * 100 if pd.notna(open_row.get('布林宽度4h')) else 0,
            '开仓_4h收盘': open_row.get('4小时收盘价', 0),
            '开仓_4h上轨': open_row.get('布林上轨4h', 0),
            '开仓_4h下轨': open_row.get('布林下轨4h', 0),
            '开仓_Armed状态': open_row.get('Armed持续4h', False),
            '开仓_HLH信号': open_row.get('HLH信号', False),
            '开仓_入场信号': open_row.get('入场信号', False),
        })
        
        # 找到平仓时间最接近的那一行
        time_diff = abs(indicators_df['时间'] - close_time)
        close_idx = time_diff.idxmin()
        close_row = indicators_df.loc[close_idx]
        
        analysis.update({
            '平仓_4h宽度%': close_row.get('布林宽度4h', 0) * 100 if pd.notna(close_row.get('布林宽度4h')) else 0,
            '平仓_4h收盘': close_row.get('4小时收盘价', 0),
            '平仓_4h下轨': close_row.get('布林下轨4h', 0),
            '平仓_Armed状态': close_row.get('Armed持续4h', False),
            '价格vs止损': (trade['close_rate'] - trade.get('stop_loss_abs', 0)) if trade.get('stop_loss_abs') else 0,
        })
        
        # 分析平仓原因
        reasons = []
        if trade.get('exit_reason') == 'stoploss_1pct':
            reasons.append('触发1%止损')
        elif trade.get('exit_reason') == 'structure_weak':
            reasons.append('结构转弱（低点创新低）')
        elif trade.get('exit_reason') == '4h_below_lower':
            reasons.append('4h失势（价格跌破下轨）')
        elif trade.get('exit_reason') == 'force_exit':
            reasons.append('强制平仓（回测结束）')
        else:
            reasons.append(trade.get('exit_reason', '未知'))
        
        analysis['平仓原因详细'] = '; '.join(reasons)
    
    trade_analysis.append(analysis)

# 6. 转换为DataFrame并导出
analysis_df = pd.DataFrame(trade_analysis)

# 添加一些计算列
if len(analysis_df) > 0:
    analysis_df['盈亏状态'] = analysis_df['盈亏%'].apply(lambda x: '盈利' if x > 0 else '亏损')
    analysis_df['累计盈亏'] = analysis_df['盈亏金额'].cumsum()

# 导出CSV
output_file = 'trade_analysis_detail.csv'
analysis_df.to_csv(output_file, index=False, encoding='utf-8-sig')

print(f"\n✅ 交易分析已导出: {output_file}")
print(f"   共 {len(analysis_df)} 笔交易")

# 7. 统计分析
if len(analysis_df) > 0:
    print("\n" + "=" * 80)
    print("交易统计")
    print("=" * 80)
    
    wins = len(analysis_df[analysis_df['盈亏%'] > 0])
    losses = len(analysis_df[analysis_df['盈亏%'] <= 0])
    
    print(f"盈利交易: {wins} 笔")
    print(f"亏损交易: {losses} 笔")
    print(f"胜率: {wins/(wins+losses)*100:.1f}%")
    print(f"\n总盈亏: {analysis_df['盈亏金额'].sum():.2f} USDT")
    print(f"平均盈亏%: {analysis_df['盈亏%'].mean():.2f}%")
    print(f"最大盈利: {analysis_df['盈亏%'].max():.2f}%")
    print(f"最大亏损: {analysis_df['盈亏%'].min():.2f}%")
    
    # 平仓原因统计
    print("\n平仓原因统计:")
    for reason, count in analysis_df['平仓原因'].value_counts().items():
        print(f"  {reason}: {count} 笔")
    
    # 显示前几笔交易
    print("\n前5笔交易:")
    display_cols = ['交易序号', '开仓时间', '平仓时间', '开仓价格', '平仓价格', '盈亏%', '平仓原因', '平仓原因详细']
    print(analysis_df[display_cols].head().to_string(index=False))

print("\n" + "=" * 80)
print("分析完成！")

