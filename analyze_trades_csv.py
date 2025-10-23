#!/usr/bin/env python3
"""
分析策略导出的交易记录CSV，计算胜率和盈亏比
"""

import pandas as pd
import numpy as np
from pathlib import Path

def analyze_trades(csv_file):
    """分析交易记录CSV"""
    
    print(f"\n{'='*70}")
    print(f"📊 交易记录分析")
    print(f"{'='*70}\n")
    print(f"📂 文件: {csv_file}\n")
    
    # 读取CSV
    try:
        df = pd.read_csv(csv_file, encoding='utf-8-sig')
        print(f"✅ 成功读取 {len(df)} 笔交易记录\n")
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return
    
    # 显示列名
    print(f"📋 CSV列名: {', '.join(df.columns)}\n")
    
    # 筛选已完成的交易
    completed = df[df['平仓时间'].notna()].copy()
    
    if len(completed) == 0:
        print("⚠️ 没有已完成的交易")
        return
    
    print(f"✅ 找到 {len(completed)} 笔已完成交易\n")
    
    # 计算统计数据
    print(f"{'='*70}")
    print(f"📊 交易统计分析")
    print(f"{'='*70}\n")
    
    total_trades = len(completed)
    winning_trades = len(completed[completed['盈亏百分比'] > 0])
    losing_trades = len(completed[completed['盈亏百分比'] <= 0])
    
    # 胜率
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # 平均盈利和亏损
    avg_win = completed[completed['盈亏百分比'] > 0]['盈亏百分比'].mean() if winning_trades > 0 else 0
    avg_loss = completed[completed['盈亏百分比'] <= 0]['盈亏百分比'].mean() if losing_trades > 0 else 0
    
    # 盈亏比
    profit_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    
    # 最大盈利和最大亏损
    max_win = completed['盈亏百分比'].max()
    max_loss = completed['盈亏百分比'].min()
    
    # 总盈利和总亏损
    total_profit = completed[completed['盈亏百分比'] > 0]['盈亏百分比'].sum()
    total_loss = completed[completed['盈亏百分比'] <= 0]['盈亏百分比'].sum()
    net_profit = completed['盈亏百分比'].sum()
    
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
    if '持仓小时' in completed.columns:
        avg_hold = completed['持仓小时'].mean()
        max_hold = completed['持仓小时'].max()
        min_hold = completed['持仓小时'].min()
        
        print(f"⏱️  持仓时间分析")
        print(f"{'-'*70}")
        print(f"  平均持仓:        {avg_hold:>6.1f} 小时 ({avg_hold/24:.1f} 天)")
        print(f"  最长持仓:        {max_hold:>6.1f} 小时 ({max_hold/24:.1f} 天)")
        print(f"  最短持仓:        {min_hold:>6.1f} 小时")
        print()
    
    # 退出原因分析
    if '平仓原因' in completed.columns:
        print(f"🚪 退出原因分析")
        print(f"{'-'*70}")
        exit_reasons = completed['平仓原因'].value_counts()
        for reason, count in exit_reasons.items():
            pct = count / total_trades * 100
            avg_profit = completed[completed['平仓原因'] == reason]['盈亏百分比'].mean()
            print(f"  {reason:<20} {count:>4} 笔 ({pct:>5.1f}%)  平均: {avg_profit:>6.2f}%")
        print()
    
    # 盈利分布
    print(f"📊 盈利分布")
    print(f"{'-'*70}")
    
    bins = [-np.inf, -5, -3, -1, 0, 1, 3, 5, np.inf]
    labels = ['<-5%', '-5%~-3%', '-3%~-1%', '-1%~0%', '0%~1%', '1%~3%', '3%~5%', '>5%']
    
    completed['profit_range'] = pd.cut(completed['盈亏百分比'], bins=bins, labels=labels)
    distribution = completed['profit_range'].value_counts().sort_index()
    
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
    
    print(f"  策略质量: {quality}\n")
    
    # 保存分析报告
    try:
        report_file = csv_file.replace('.csv', '_analysis.txt')
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"交易记录分析报告\n")
            f.write(f"{'='*70}\n")
            f.write(f"分析时间: {pd.Timestamp.now()}\n")
            f.write(f"数据文件: {csv_file}\n")
            f.write(f"{'='*70}\n\n")
            f.write(f"总交易数: {total_trades}\n")
            f.write(f"胜率: {win_rate:.2f}%\n")
            f.write(f"盈亏比: {profit_loss_ratio:.2f}\n")
            f.write(f"盈利因子: {profit_factor:.2f}\n")
            f.write(f"净盈利: {net_profit:.2f}%\n")
        
        print(f"📄 分析报告已保存: {report_file}\n")
    except Exception as e:
        print(f"⚠️ 保存报告失败: {e}\n")


def find_trades_csv():
    """查找交易记录CSV文件"""
    debug_dir = Path('user_data/debug')
    
    if not debug_dir.exists():
        return []
    
    csv_files = list(debug_dir.glob('trades_history_*.csv'))
    return csv_files


def main():
    """主函数"""
    
    print("\n" + "="*70)
    print("📊 交易记录分析工具")
    print("="*70)
    
    # 查找CSV文件
    csv_files = find_trades_csv()
    
    if not csv_files:
        print("\n❌ 未找到交易记录CSV文件")
        print("\n💡 提示:")
        print("  1. 先运行回测生成交易记录")
        print("  2. 文件应在 user_data/debug/ 目录下")
        print("  3. 文件名格式: trades_history_<交易对>.csv")
        return
    
    print(f"\n找到 {len(csv_files)} 个交易记录文件:\n")
    
    for i, csv_file in enumerate(csv_files, 1):
        print(f"  {i}. {csv_file.name}")
    
    print()
    
    # 选择文件
    if len(csv_files) == 1:
        selected_file = csv_files[0]
        analyze_trades(str(selected_file))
    else:
        try:
            choice = input(f"请选择要分析的文件 (1-{len(csv_files)}, 0=全部): ").strip()
            
            if choice == '0':
                # 分析所有文件
                for csv_file in csv_files:
                    analyze_trades(str(csv_file))
            else:
                idx = int(choice) - 1
                if 0 <= idx < len(csv_files):
                    analyze_trades(str(csv_files[idx]))
                else:
                    print("❌ 无效的选择")
        except (ValueError, KeyboardInterrupt):
            print("\n❌ 已取消")


if __name__ == '__main__':
    main()

