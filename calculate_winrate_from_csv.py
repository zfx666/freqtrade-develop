#!/usr/bin/env python3
"""
从CSV文件计算胜率和盈亏比
通过分析入场信号后的价格走势来估算交易表现
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

def calculate_from_csv(csv_file, stop_loss_pct=-0.01, take_profit_pct=0.05, max_hold_hours=72):
    """
    从CSV文件计算模拟交易的胜率和盈亏比
    
    参数:
        csv_file: CSV文件路径
        stop_loss_pct: 止损百分比（默认-1%）
        take_profit_pct: 止盈百分比（默认5%）
        max_hold_hours: 最大持仓时间（默认72小时）
    """
    
    print(f"\n{'='*70}")
    print(f"📊 从CSV计算胜率和盈亏比")
    print(f"{'='*70}\n")
    print(f"📂 文件: {csv_file}")
    print(f"⚙️  参数: 止损={stop_loss_pct*100:.1f}%, 止盈={take_profit_pct*100:.1f}%, 最大持仓={max_hold_hours}小时\n")
    
    # 读取CSV
    try:
        df = pd.read_csv(csv_file, encoding='utf-8-sig')
        print(f"✅ 成功读取 {len(df)} 行数据\n")
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return None
    
    # 查找必要的列
    entry_col = None
    for col in ['入场信号', 'enter_long']:
        if col in df.columns:
            entry_col = col
            break
    
    close_col = None
    for col in ['收盘价', 'close']:
        if col in df.columns:
            close_col = col
            break
    
    if entry_col is None or close_col is None:
        print(f"❌ 缺少必要的列")
        print(f"   需要: 入场信号/enter_long 和 收盘价/close")
        print(f"   可用列: {', '.join(df.columns)}")
        return None
    
    # 查找入场信号
    entries = df[df[entry_col] == 1].copy()
    
    if len(entries) == 0:
        print(f"⚠️ 未找到任何入场信号")
        return None
    
    print(f"📈 找到 {len(entries)} 个入场信号\n")
    print(f"🔄 模拟交易执行...\n")
    
    # 模拟每笔交易
    trades = []
    
    for idx in entries.index:
        entry_idx = df.index.get_loc(idx)
        entry_price = df.loc[idx, close_col]
        entry_time = df.loc[idx, '时间'] if '时间' in df.columns else idx
        
        # 检查后续价格走势
        exit_price = None
        exit_reason = None
        exit_idx = None
        profit_pct = 0
        
        # 扫描后续K线（最多max_hold_hours根）
        for i in range(1, min(max_hold_hours + 1, len(df) - entry_idx)):
            future_idx = entry_idx + i
            if future_idx >= len(df):
                break
            
            current_price = df.iloc[future_idx][close_col]
            current_change = (current_price - entry_price) / entry_price
            
            # 检查止损
            if current_change <= stop_loss_pct:
                exit_price = entry_price * (1 + stop_loss_pct)
                exit_reason = 'stop_loss'
                exit_idx = future_idx
                profit_pct = stop_loss_pct * 100
                break
            
            # 检查止盈
            if current_change >= take_profit_pct:
                exit_price = entry_price * (1 + take_profit_pct)
                exit_reason = 'take_profit'
                exit_idx = future_idx
                profit_pct = take_profit_pct * 100
                break
        
        # 如果没有触发止损/止盈，按最大持仓时间出场
        if exit_price is None:
            if entry_idx + max_hold_hours < len(df):
                exit_idx = entry_idx + max_hold_hours
                exit_price = df.iloc[exit_idx][close_col]
                profit_pct = (exit_price - entry_price) / entry_price * 100
                exit_reason = 'max_hold'
            else:
                # 如果数据不够，使用最后一根K线
                exit_idx = len(df) - 1
                exit_price = df.iloc[exit_idx][close_col]
                profit_pct = (exit_price - entry_price) / entry_price * 100
                exit_reason = 'end_of_data'
        
        # 记录交易
        hold_hours = exit_idx - entry_idx if exit_idx else 0
        exit_time = df.iloc[exit_idx]['时间'] if '时间' in df.columns and exit_idx else None
        
        trades.append({
            'entry_time': entry_time,
            'exit_time': exit_time,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'profit_pct': profit_pct,
            'exit_reason': exit_reason,
            'hold_hours': hold_hours
        })
    
    # 转换为DataFrame
    trades_df = pd.DataFrame(trades)
    
    # 计算统计数据
    print(f"{'='*70}")
    print(f"📊 交易统计分析（模拟）")
    print(f"{'='*70}\n")
    
    total_trades = len(trades_df)
    winning_trades = len(trades_df[trades_df['profit_pct'] > 0])
    losing_trades = len(trades_df[trades_df['profit_pct'] <= 0])
    
    # 胜率
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # 平均盈利和亏损
    avg_win = trades_df[trades_df['profit_pct'] > 0]['profit_pct'].mean() if winning_trades > 0 else 0
    avg_loss = trades_df[trades_df['profit_pct'] <= 0]['profit_pct'].mean() if losing_trades > 0 else 0
    
    # 盈亏比
    profit_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    
    # 最大盈利和最大亏损
    max_win = trades_df['profit_pct'].max()
    max_loss = trades_df['profit_pct'].min()
    
    # 总盈利和总亏损
    total_profit = trades_df[trades_df['profit_pct'] > 0]['profit_pct'].sum()
    total_loss = trades_df[trades_df['profit_pct'] <= 0]['profit_pct'].sum()
    net_profit = trades_df['profit_pct'].sum()
    
    # 盈利因子
    profit_factor = abs(total_profit / total_loss) if total_loss != 0 else 0
    
    # 打印基本统计
    print(f"📈 基本统计")
    print(f"{'-'*70}")
    print(f"  总交易数:        {total_trades:>6} 笔")
    print(f"  盈利交易:        {winning_trades:>6} 笔  ({winning_trades/total_trades*100:>5.1f}%)")
    print(f"  亏损交易:        {losing_trades:>6} 笔  ({losing_trades/total_trades*100:>5.1f}%)")
    print()
    
    print(f"🎯 胜率分析")
    print(f"{'-'*70}")
    print(f"  胜率:            {win_rate:>6.2f}%")
    print()
    
    print(f"💰 盈亏分析")
    print(f"{'-'*70}")
    print(f"  平均盈利:        {avg_win:>6.2f}%")
    print(f"  平均亏损:        {avg_loss:>6.2f}%")
    print(f"  盈亏比:          {profit_loss_ratio:>6.2f}  (平均盈利/平均亏损)")
    print()
    print(f"  最大盈利:        {max_win:>6.2f}%")
    print(f"  最大亏损:        {max_loss:>6.2f}%")
    print()
    print(f"  总盈利:          {total_profit:>6.2f}%")
    print(f"  总亏损:          {total_loss:>6.2f}%")
    print(f"  净盈利:          {net_profit:>6.2f}%")
    print(f"  盈利因子:        {profit_factor:>6.2f}  (总盈利/总亏损)")
    print()
    
    # 持仓时间分析
    avg_hold = trades_df['hold_hours'].mean()
    max_hold = trades_df['hold_hours'].max()
    min_hold = trades_df['hold_hours'].min()
    
    print(f"⏱️  持仓时间分析")
    print(f"{'-'*70}")
    print(f"  平均持仓:        {avg_hold:>6.0f} 小时 ({avg_hold/24:.1f} 天)")
    print(f"  最长持仓:        {max_hold:>6.0f} 小时 ({max_hold/24:.1f} 天)")
    print(f"  最短持仓:        {min_hold:>6.0f} 小时")
    print()
    
    # 退出原因分析
    print(f"🚪 退出原因分析")
    print(f"{'-'*70}")
    exit_reasons = trades_df['exit_reason'].value_counts()
    for reason, count in exit_reasons.items():
        pct = count / total_trades * 100
        avg_profit = trades_df[trades_df['exit_reason'] == reason]['profit_pct'].mean()
        reason_name = {
            'stop_loss': '止损',
            'take_profit': '止盈',
            'max_hold': '最大持仓',
            'end_of_data': '数据结束'
        }.get(reason, reason)
        print(f"  {reason_name:<12} {count:>4} 笔 ({pct:>5.1f}%)  平均: {avg_profit:>6.2f}%")
    print()
    
    # 盈利分布
    print(f"📊 盈利分布")
    print(f"{'-'*70}")
    
    bins = [-np.inf, -5, -3, -1, 0, 1, 3, 5, np.inf]
    labels = ['<-5%', '-5%~-3%', '-3%~-1%', '-1%~0%', '0%~1%', '1%~3%', '3%~5%', '>5%']
    
    trades_df['profit_range'] = pd.cut(trades_df['profit_pct'], bins=bins, labels=labels)
    distribution = trades_df['profit_range'].value_counts().sort_index()
    
    for range_label, count in distribution.items():
        pct = count / total_trades * 100
        bar = '█' * int(pct / 2)
        print(f"  {range_label:<12} {count:>4} 笔 ({pct:>5.1f}%)  {bar}")
    print()
    
    # 关键指标总结
    print(f"{'='*70}")
    print(f"🎯 关键指标总结")
    print(f"{'='*70}")
    print(f"  ✅ 胜率:          {win_rate:.2f}%")
    print(f"  💰 盈亏比:        {profit_loss_ratio:.2f}")
    print(f"  📈 盈利因子:      {profit_factor:.2f}")
    print(f"  💵 净盈利:        {net_profit:.2f}%")
    print(f"  📊 平均单笔:      {net_profit/total_trades:.2f}%")
    print(f"{'='*70}\n")
    
    # 策略评估
    print(f"📝 策略评估（基于模拟交易）")
    print(f"{'-'*70}")
    
    if win_rate >= 50 and profit_loss_ratio >= 2:
        quality = "🌟 优秀"
    elif win_rate >= 40 and profit_loss_ratio >= 1.5:
        quality = "✅ 良好"
    elif win_rate >= 30 and profit_loss_ratio >= 1.2:
        quality = "⚠️  一般"
    else:
        quality = "❌ 需要优化"
    
    print(f"  策略质量: {quality}")
    print()
    
    if win_rate < 40:
        print("  💡 建议: 胜率较低，可以考虑:")
        print("     - 降低宽度阈值（更严格的缩口条件）")
        print("     - 增加更多入场过滤条件")
        print("     - 优化HLH结构判断逻辑")
    
    if profit_loss_ratio < 1.5:
        print("  💡 建议: 盈亏比偏低，可以考虑:")
        print("     - 调整止损止盈参数")
        print("     - 优化出场时机")
        print("     - 使用跟踪止盈")
    
    print()
    
    # 保存结果
    try:
        output_dir = Path('user_data/analysis')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存交易明细
        trades_file = output_dir / 'simulated_trades.csv'
        trades_df.to_csv(trades_file, index=False, encoding='utf-8-sig')
        print(f"📄 交易明细已保存: {trades_file}")
        
        # 保存统计报告
        report_file = output_dir / 'winrate_report.txt'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"胜率和盈亏比分析报告（基于CSV模拟）\n")
            f.write(f"{'='*70}\n")
            f.write(f"分析时间: {pd.Timestamp.now()}\n")
            f.write(f"数据文件: {csv_file}\n")
            f.write(f"{'='*70}\n\n")
            f.write(f"参数设置:\n")
            f.write(f"  止损: {stop_loss_pct*100:.1f}%\n")
            f.write(f"  止盈: {take_profit_pct*100:.1f}%\n")
            f.write(f"  最大持仓: {max_hold_hours} 小时\n\n")
            f.write(f"总交易数: {total_trades}\n")
            f.write(f"胜率: {win_rate:.2f}%\n")
            f.write(f"盈亏比: {profit_loss_ratio:.2f}\n")
            f.write(f"盈利因子: {profit_factor:.2f}\n")
            f.write(f"净盈利: {net_profit:.2f}%\n")
        
        print(f"📄 统计报告已保存: {report_file}\n")
        
    except Exception as e:
        print(f"⚠️ 保存结果失败: {e}\n")
    
    print(f"{'='*70}\n")
    print("ℹ️  注意:")
    print("  - 这是基于CSV数据的模拟计算")
    print("  - 实际回测结果可能与此不同")
    print("  - 可以调整止损止盈参数重新计算")
    print(f"{'='*70}\n")
    
    return {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'profit_loss_ratio': profit_loss_ratio,
        'profit_factor': profit_factor,
        'net_profit': net_profit
    }


def find_csv_files():
    """查找CSV文件"""
    debug_dir = Path('user_data/debug')
    
    if not debug_dir.exists():
        return []
    
    csv_files = list(debug_dir.glob('BollingerHLH_*_full.csv'))
    return csv_files


def main():
    """主函数"""
    
    print("\n" + "="*70)
    print("📊 从CSV计算胜率和盈亏比")
    print("="*70)
    
    # 查找CSV文件
    csv_files = find_csv_files()
    
    if not csv_files:
        print("\n❌ 未找到CSV文件")
        print("\n💡 提示:")
        print("  1. 先运行回测生成CSV文件")
        print("  2. CSV文件应在 user_data/debug/ 目录下")
        print("  3. 文件名格式: BollingerHLH_<交易对>_1h_full.csv")
        return
    
    print(f"\n找到 {len(csv_files)} 个CSV文件:\n")
    
    for i, csv_file in enumerate(csv_files, 1):
        print(f"  {i}. {csv_file.name}")
    
    print()
    
    # 选择文件
    if len(csv_files) == 1:
        selected_file = csv_files[0]
    else:
        try:
            choice = input(f"请选择要分析的文件 (1-{len(csv_files)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(csv_files):
                selected_file = csv_files[idx]
            else:
                print("❌ 无效的选择")
                return
        except (ValueError, KeyboardInterrupt):
            print("\n❌ 已取消")
            return
    
    # 参数设置
    print("\n⚙️  参数设置（按Enter使用默认值）:")
    
    try:
        stop_loss = input("  止损百分比 [默认: -1.0%]: ").strip()
        stop_loss_pct = float(stop_loss) / 100 if stop_loss else -0.01
        
        take_profit = input("  止盈百分比 [默认: 5.0%]: ").strip()
        take_profit_pct = float(take_profit) / 100 if take_profit else 0.05
        
        max_hold = input("  最大持仓时间（小时） [默认: 72]: ").strip()
        max_hold_hours = int(max_hold) if max_hold else 72
        
    except ValueError:
        print("❌ 无效的参数")
        return
    
    # 执行分析
    calculate_from_csv(
        str(selected_file),
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        max_hold_hours=max_hold_hours
    )


if __name__ == '__main__':
    main()

