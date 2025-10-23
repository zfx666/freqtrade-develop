#!/usr/bin/env python3
"""
计算策略的胜率和盈亏比
结合CSV指标数据和回测交易记录
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
import sys

def load_trades():
    """加载回测交易记录"""
    backtest_dir = Path('user_data/backtest_results')
    
    # 查找最新的交易记录文件
    trade_files = []
    
    # 查找 *-trades.json 或 *-trades.csv
    trade_files.extend(backtest_dir.glob('*-trades.json'))
    trade_files.extend(backtest_dir.glob('*-trades.csv'))
    
    if not trade_files:
        print("❌ 未找到交易记录文件")
        print("💡 提示: 运行回测时使用 --export trades 参数")
        return None
    
    # 使用最新的文件
    latest_file = max(trade_files, key=lambda x: x.stat().st_mtime)
    print(f"📂 加载交易记录: {latest_file.name}")
    
    try:
        if latest_file.suffix == '.json':
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    df = pd.DataFrame(data)
                else:
                    df = pd.DataFrame([data])
        else:  # CSV
            df = pd.read_csv(latest_file)
        
        print(f"✅ 成功加载 {len(df)} 笔交易\n")
        return df
        
    except Exception as e:
        print(f"❌ 加载失败: {e}")
        return None


def calculate_statistics(trades_df):
    """计算胜率和盈亏比"""
    
    if trades_df is None or len(trades_df) == 0:
        print("❌ 没有交易数据")
        return
    
    print(f"\n{'='*70}")
    print(f"📊 交易统计分析")
    print(f"{'='*70}\n")
    
    # 检查必要的列
    profit_col = None
    for col in ['profit_ratio', 'profit_percent', 'profit_abs', 'close_profit_abs']:
        if col in trades_df.columns:
            profit_col = col
            break
    
    if profit_col is None:
        print("❌ 未找到盈利数据列")
        print(f"可用列: {', '.join(trades_df.columns)}")
        return
    
    # 转换为百分比（如果是ratio格式）
    if 'ratio' in profit_col:
        trades_df['profit_pct'] = trades_df[profit_col] * 100
    else:
        trades_df['profit_pct'] = trades_df[profit_col]
    
    # 基本统计
    total_trades = len(trades_df)
    winning_trades = len(trades_df[trades_df['profit_pct'] > 0])
    losing_trades = len(trades_df[trades_df['profit_pct'] <= 0])
    
    # 胜率
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # 平均盈利和亏损
    avg_win = trades_df[trades_df['profit_pct'] > 0]['profit_pct'].mean() if winning_trades > 0 else 0
    avg_loss = trades_df[trades_df['profit_pct'] <= 0]['profit_pct'].mean() if losing_trades > 0 else 0
    
    # 盈亏比（平均盈利/平均亏损的绝对值）
    profit_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    
    # 最大盈利和最大亏损
    max_win = trades_df['profit_pct'].max()
    max_loss = trades_df['profit_pct'].min()
    
    # 总盈利和总亏损
    total_profit = trades_df[trades_df['profit_pct'] > 0]['profit_pct'].sum()
    total_loss = trades_df[trades_df['profit_pct'] <= 0]['profit_pct'].sum()
    net_profit = trades_df['profit_pct'].sum()
    
    # 盈利因子（总盈利/总亏损的绝对值）
    profit_factor = abs(total_profit / total_loss) if total_loss != 0 else 0
    
    # 打印结果
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
    
    # 交易持续时间分析
    if 'trade_duration' in trades_df.columns:
        print(f"⏱️  持仓时间分析")
        print(f"{'-'*70}")
        
        # 转换持续时间（分钟）
        if trades_df['trade_duration'].dtype == 'object':
            # 如果是字符串格式（如 "2:30:00"），需要转换
            pass
        else:
            avg_duration = trades_df['trade_duration'].mean()
            max_duration = trades_df['trade_duration'].max()
            min_duration = trades_df['trade_duration'].min()
            
            print(f"  平均持仓:        {avg_duration:>6.0f} 分钟 ({avg_duration/60:.1f} 小时)")
            print(f"  最长持仓:        {max_duration:>6.0f} 分钟 ({max_duration/60:.1f} 小时)")
            print(f"  最短持仓:        {min_duration:>6.0f} 分钟 ({min_duration/60:.1f} 小时)")
            print()
    
    # 退出原因分析
    if 'exit_reason' in trades_df.columns or 'sell_reason' in trades_df.columns:
        exit_col = 'exit_reason' if 'exit_reason' in trades_df.columns else 'sell_reason'
        
        print(f"🚪 退出原因分析")
        print(f"{'-'*70}")
        
        exit_reasons = trades_df[exit_col].value_counts()
        for reason, count in exit_reasons.items():
            pct = count / total_trades * 100
            avg_profit = trades_df[trades_df[exit_col] == reason]['profit_pct'].mean()
            print(f"  {reason:<20} {count:>4} 笔 ({pct:>5.1f}%)  平均: {avg_profit:>6.2f}%")
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
        bar = '█' * int(pct / 2)  # 每2%一个█
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
    
    # 评估策略质量
    print(f"📝 策略评估")
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
        print("     - 收紧入场条件（减少宽度阈值）")
        print("     - 增加更多过滤条件")
        print("     - 优化HLH结构判断逻辑")
    
    if profit_loss_ratio < 1.5:
        print("  💡 建议: 盈亏比偏低，可以考虑:")
        print("     - 优化止损策略")
        print("     - 提高目标利润")
        print("     - 改进出场信号")
    
    print()
    
    # 保存统计结果
    try:
        output_file = 'user_data/backtest_results/winrate_analysis.txt'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"胜率和盈亏比分析报告\n")
            f.write(f"{'='*70}\n")
            f.write(f"分析时间: {pd.Timestamp.now()}\n")
            f.write(f"{'='*70}\n\n")
            f.write(f"总交易数: {total_trades}\n")
            f.write(f"胜率: {win_rate:.2f}%\n")
            f.write(f"盈亏比: {profit_loss_ratio:.2f}\n")
            f.write(f"盈利因子: {profit_factor:.2f}\n")
            f.write(f"净盈利: {net_profit:.2f}%\n")
            f.write(f"\n详细分析请查看控制台输出\n")
        
        print(f"📄 分析报告已保存: {output_file}\n")
    except Exception as e:
        print(f"⚠️ 保存报告失败: {e}\n")
    
    return {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'profit_loss_ratio': profit_loss_ratio,
        'profit_factor': profit_factor,
        'net_profit': net_profit,
        'avg_win': avg_win,
        'avg_loss': avg_loss
    }


def main():
    """主函数"""
    
    print("\n" + "="*70)
    print("📊 策略胜率和盈亏比计算工具")
    print("="*70 + "\n")
    
    # 加载交易记录
    trades_df = load_trades()
    
    if trades_df is None:
        print("\n💡 请先运行回测:")
        print("  freqtrade backtesting \\")
        print("    --strategy Bollinger4h1hStructureStrategy \\")
        print("    --config user_data/config_bollinger_4h1h.json \\")
        print("    --timerange 20241010-20251010 \\")
        print("    --export trades")
        return
    
    # 计算统计数据
    stats = calculate_statistics(trades_df)
    
    if stats:
        print(f"✅ 分析完成！\n")


if __name__ == '__main__':
    main()

