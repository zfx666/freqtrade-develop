#!/usr/bin/env python3
"""
测试布林带4h+1h结构策略的脚本
包含回测、优化参数和分析功能
"""

import subprocess
import sys
import os
from datetime import datetime, timedelta

def run_command(command, description):
    """运行命令并显示结果"""
    print(f"\n{'='*60}")
    print(f"执行: {description}")
    print(f"命令: {command}")
    print('='*60)
    
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        if result.stdout:
            print("标准输出:")
            print(result.stdout)
        
        if result.stderr:
            print("错误输出:")
            print(result.stderr)
        
        if result.returncode != 0:
            print(f"命令执行失败，返回码: {result.returncode}")
            return False
        else:
            print("命令执行成功!")
            return True
            
    except Exception as e:
        print(f"执行命令时出错: {e}")
        return False

def main():
    """主函数"""
    strategy_name = "Bollinger4h1hStructureStrategy"
    config_file = "user_data/config_bollinger_4h1h.json"
    
    # 检查策略文件是否存在
    strategy_file = f"user_data/strategies/{strategy_name}.py"
    if not os.path.exists(strategy_file):
        print(f"策略文件不存在: {strategy_file}")
        return
    
    # 检查配置文件是否存在
    if not os.path.exists(config_file):
        print(f"配置文件不存在: {config_file}")
        return
    
    print("布林带4h+1h结构策略测试脚本")
    print(f"策略: {strategy_name}")
    print(f"配置: {config_file}")
    
    while True:
        print("\n请选择操作:")
        print("1. 下载数据 (BTC/USDT 1h + 4h)")
        print("2. 策略回测 (最近6个月)")
        print("3. 策略回测 (最近1年)")
        print("4. 参数优化")
        print("5. 显示策略参数")
        print("6. 分析回测结果")
        print("7. 退出")
        
        choice = input("\n请输入选择 (1-7): ").strip()
        
        if choice == '1':
            # 下载数据
            print("\n下载BTC/USDT数据...")
            
            # 下载1h数据
            cmd_1h = f"freqtrade download-data --config {config_file} --timeframe 1h --days 400"
            run_command(cmd_1h, "下载1小时数据")
            
            # 下载4h数据
            cmd_4h = f"freqtrade download-data --config {config_file} --timeframe 4h --days 400"
            run_command(cmd_4h, "下载4小时数据")
            
        elif choice == '2':
            # 6个月回测
            end_date = datetime.now()
            start_date = end_date - timedelta(days=180)
            
            cmd = f"""freqtrade backtesting --config {config_file} \\
                --strategy {strategy_name} \\
                --timerange {start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')} \\
                --breakdown day \\
                --export signals"""
            
            run_command(cmd, "6个月回测")
            
        elif choice == '3':
            # 1年回测
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)
            
            cmd = f"""freqtrade backtesting --config {config_file} \\
                --strategy {strategy_name} \\
                --timerange {start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')} \\
                --breakdown day \\
                --export signals"""
            
            run_command(cmd, "1年回测")
            
        elif choice == '4':
            # 参数优化
            end_date = datetime.now()
            start_date = end_date - timedelta(days=180)
            
            cmd = f"""freqtrade hyperopt --config {config_file} \\
                --strategy {strategy_name} \\
                --timerange {start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')} \\
                --hyperopt-loss SharpeHyperOptLoss \\
                --spaces buy sell \\
                --epochs 100 \\
                --jobs 1"""
            
            run_command(cmd, "参数优化")
            
        elif choice == '5':
            # 显示策略参数
            cmd = f"freqtrade list-strategies --strategy {strategy_name} --config {config_file}"
            run_command(cmd, "显示策略参数")
            
        elif choice == '6':
            # 分析回测结果
            print("\\n分析最新的回测结果...")
            
            # 显示回测报告
            cmd_report = "freqtrade backtesting-analysis --analysis-groups 0 1 2"
            run_command(cmd_report, "生成分析报告")
            
            # 显示交易列表
            cmd_trades = "freqtrade backtesting-analysis --analysis-groups 4"
            run_command(cmd_trades, "显示交易详情")
            
        elif choice == '7':
            print("退出程序...")
            break
            
        else:
            print("无效选择，请重新输入!")

if __name__ == "__main__":
    main()
