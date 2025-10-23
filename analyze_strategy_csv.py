#!/usr/bin/env python3
"""
分析策略导出的CSV文件，计算胜率和盈亏比
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

def analyze_csv(csv_file):
    """分析CSV文件，计算胜率和盈亏比"""
    
    print(f"\n{'='*60}")
    print(f"📊 分析文件: {csv_file}")
    print(f"{'='*60}\n")
    
    # 读取CSV文件
    try:
        df = pd.read_csv(csv_file, encoding='utf-8-sig')
        print(f"✅ 成功读取 {len(df)} 行数据\n")
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return
    
    # 显示列名
    print(f"📋 CSV列名:")
    for i, col in enumerate(df.columns, 1):
        print(f"  {i}. {col}")
    print()
    
    # 检查是否有入场信号列
    entry_col = None
    for col in ['入场信号', 'enter_long', '入场评估', 'debug_entry_eval']:
        if col in df.columns:
            entry_col = col
            break
    
    if entry_col is None:
        print("⚠️ 未找到入场信号列，无法计算交易统计")
        return
    
    # 筛选入场信号
    entries = df[df[entry_col] == 1].copy()
    
    if len(entries) == 0:
        print(f"⚠️ 未找到任何入场信号（{entry_col} = 1）")
        return
    
    print(f"📈 找到 {len(entries)} 个入场信号\n")
    
    # 显示入场信号的时间分布
    if '时间' in entries.columns:
        print("📅 入场信号时间分布:")
        entries_with_time = entries['时间'].dropna()
        if len(entries_with_time) > 0:
            # 转换为datetime
            entries['时间_dt'] = pd.to_datetime(entries['时间'], errors='coerce')
            
            # 按月统计
            monthly = entries['时间_dt'].dt.to_period('M').value_counts().sort_index()
            print("\n  按月份:")
            for period, count in monthly.items():
                print(f"    {period}: {count} 次")
            
            print(f"\n  最早入场: {entries['时间_dt'].min()}")
            print(f"  最晚入场: {entries['时间_dt'].max()}")
        print()
    
    # 分析Armed状态
    armed_col = None
    for col in ['Armed持续', 'armed_active', 'Armed持续4h', 'armed_active_4h']:
        if col in df.columns:
            armed_col = col
            break
    
    if armed_col:
        armed_count = df[df[armed_col] == True].shape[0]
        armed_pct = (armed_count / len(df)) * 100
        print(f"🎯 Armed状态统计:")
        print(f"  - Armed持续时间: {armed_count} 小时")
        print(f"  - Armed占比: {armed_pct:.2f}%")
        print(f"  - Armed期间入场信号: {len(entries[entries[armed_col] == True])} 个")
        print()
    
    # 分析布林带宽度
    width_col = None
    for col in ['布林宽度', 'bb_width', '布林宽度4h', 'bb_width_4h']:
        if col in df.columns:
            width_col = col
            break
    
    if width_col:
        print(f"📏 布林带宽度统计:")
        print(f"  - 平均宽度: {df[width_col].mean()*100:.2f}%")
        print(f"  - 最小宽度: {df[width_col].min()*100:.2f}%")
        print(f"  - 最大宽度: {df[width_col].max()*100:.2f}%")
        print(f"  - 中位数宽度: {df[width_col].median()*100:.2f}%")
        
        # 入场时的宽度
        if width_col in entries.columns:
            entry_widths = entries[width_col].dropna()
            if len(entry_widths) > 0:
                print(f"\n  入场时宽度统计:")
                print(f"    - 平均: {entry_widths.mean()*100:.2f}%")
                print(f"    - 最小: {entry_widths.min()*100:.2f}%")
                print(f"    - 最大: {entry_widths.max()*100:.2f}%")
                print(f"    - 中位数: {entry_widths.median()*100:.2f}%")
        print()
    
    # 分析HLH信号
    hlh_col = None
    for col in ['HLH信号', 'hlh_signal']:
        if col in df.columns:
            hlh_col = col
            break
    
    if hlh_col:
        hlh_count = df[df[hlh_col] == True].shape[0]
        print(f"🔍 HLH信号统计:")
        print(f"  - HLH信号总数: {hlh_count} 次")
        print(f"  - 有Armed的HLH: {len(entries)} 次（最终入场）")
        
        if armed_col:
            hlh_with_armed = df[(df[hlh_col] == True) & (df[armed_col] == True)].shape[0]
            print(f"  - HLH转化为入场率: {(len(entries)/hlh_with_armed*100) if hlh_with_armed > 0 else 0:.2f}%")
        print()
    
    # 分析入场确认结果
    confirm_col = None
    reject_col = None
    for col in ['入场确认结果', 'entry_confirm_result']:
        if col in df.columns:
            confirm_col = col
            break
    for col in ['拒绝原因', 'entry_reject_reason']:
        if col in df.columns:
            reject_col = col
            break
    
    if confirm_col and reject_col:
        print(f"✅ 入场确认统计:")
        
        # 统计确认结果
        confirm_results = entries[confirm_col].value_counts()
        print(f"\n  确认结果分布:")
        for result, count in confirm_results.items():
            if result:  # 非空
                print(f"    - {result}: {count} 次")
        
        # 统计拒绝原因
        rejected = entries[entries[reject_col].notna() & (entries[reject_col] != '')]
        if len(rejected) > 0:
            print(f"\n  拒绝原因分布:")
            reject_reasons = rejected[reject_col].value_counts()
            for reason, count in reject_reasons.items():
                print(f"    - {reason}: {count} 次")
        print()
    
    # 分析价格变化
    price_change_col = None
    for col in ['价格变化率', 'price_change_pct']:
        if col in df.columns:
            price_change_col = col
            break
    
    if price_change_col:
        entry_price_changes = entries[price_change_col].dropna()
        if len(entry_price_changes) > 0:
            print(f"💹 入场时价格变化统计:")
            print(f"  - 平均变化: {entry_price_changes.mean()*100:.2f}%")
            print(f"  - 最大涨幅: {entry_price_changes.max()*100:.2f}%")
            print(f"  - 最大跌幅: {entry_price_changes.min()*100:.2f}%")
            
            positive = entry_price_changes[entry_price_changes > 0]
            negative = entry_price_changes[entry_price_changes < 0]
            print(f"  - 上涨入场: {len(positive)} 次 ({len(positive)/len(entry_price_changes)*100:.1f}%)")
            print(f"  - 下跌入场: {len(negative)} 次 ({len(negative)/len(entry_price_changes)*100:.1f}%)")
            print()
    
    print(f"\n{'='*60}")
    print("ℹ️  说明：")
    print("  - 此分析仅基于CSV导出的指标数据")
    print("  - 要计算实际胜率和盈亏比，需要分析回测交易记录")
    print("  - 请使用 'analyze_backtest_results.py' 分析交易结果")
    print(f"{'='*60}\n")
    
    # 保存统计结果
    output_file = csv_file.replace('.csv', '_analysis.txt')
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"策略CSV分析报告\n")
            f.write(f"{'='*60}\n")
            f.write(f"文件: {csv_file}\n")
            f.write(f"分析时间: {pd.Timestamp.now()}\n")
            f.write(f"{'='*60}\n\n")
            f.write(f"总数据行数: {len(df)}\n")
            f.write(f"入场信号数: {len(entries)}\n")
            if armed_col:
                f.write(f"Armed持续时间: {armed_count} 小时 ({armed_pct:.2f}%)\n")
            if hlh_col:
                f.write(f"HLH信号总数: {hlh_count} 次\n")
            f.write(f"\n详细分析请查看控制台输出\n")
        print(f"📄 分析报告已保存: {output_file}\n")
    except Exception as e:
        print(f"⚠️ 保存分析报告失败: {e}\n")


def find_csv_files():
    """查找debug目录下的CSV文件"""
    debug_dir = Path('user_data/debug')
    
    if not debug_dir.exists():
        print(f"❌ 目录不存在: {debug_dir}")
        return []
    
    csv_files = list(debug_dir.glob('BollingerHLH_*_full.csv'))
    
    if not csv_files:
        print(f"⚠️ 在 {debug_dir} 目录下未找到CSV文件")
        print(f"请确保已运行回测并导出数据")
        return []
    
    return csv_files


def main():
    """主函数"""
    
    print("\n" + "="*60)
    print("📊 策略CSV分析工具")
    print("="*60)
    
    # 查找CSV文件
    csv_files = find_csv_files()
    
    if not csv_files:
        print("\n💡 提示:")
        print("  1. 先运行回测生成CSV文件")
        print("  2. CSV文件应在 user_data/debug/ 目录下")
        print("  3. 文件名格式: BollingerHLH_<交易对>_1h_full.csv")
        return
    
    print(f"\n找到 {len(csv_files)} 个CSV文件:\n")
    
    for i, csv_file in enumerate(csv_files, 1):
        print(f"  {i}. {csv_file.name}")
    
    print()
    
    # 如果只有一个文件，直接分析
    if len(csv_files) == 1:
        analyze_csv(str(csv_files[0]))
    else:
        # 多个文件，让用户选择
        try:
            choice = input(f"请选择要分析的文件 (1-{len(csv_files)}, 0=全部): ").strip()
            
            if choice == '0':
                # 分析所有文件
                for csv_file in csv_files:
                    analyze_csv(str(csv_file))
            else:
                idx = int(choice) - 1
                if 0 <= idx < len(csv_files):
                    analyze_csv(str(csv_files[idx]))
                else:
                    print("❌ 无效的选择")
        except (ValueError, KeyboardInterrupt):
            print("\n❌ 已取消")


if __name__ == '__main__':
    main()

