"""
分析Freqtrade回测结果
支持从backtest结果CSV文件读取数据并进行详细分析
"""
import pandas as pd
import sys
from pathlib import Path

def analyze_trades(csv_file):
    """分析交易数据"""
    try:
        # 读取CSV文件
        df = pd.read_csv(csv_file)
        print(f"\n成功读取文件: {csv_file}")
        print(f"总交易笔数: {len(df)}")
        
        # 检查必需的列
        required_cols = ['open_date', 'close_date', 'profit_ratio', 'exit_reason']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"\n错误：缺少必需的列: {missing_cols}")
            print(f"可用的列: {df.columns.tolist()}")
            return
        
        # 转换日期
        df['open_date'] = pd.to_datetime(df['open_date'])
        df['close_date'] = pd.to_datetime(df['close_date'])
        df['duration'] = (df['close_date'] - df['open_date']).dt.total_seconds() / 3600  # 转换为小时
        
        # 转换利润为百分比
        df['profit_pct'] = df['profit_ratio'] * 100
        
        print("\n" + "="*80)
        print("胜率统计")
        print("="*80)
        
        # 基本统计
        total_trades = len(df)
        winning_trades = len(df[df['profit_pct'] > 0])
        losing_trades = len(df[df['profit_pct'] < 0])
        breakeven_trades = len(df[df['profit_pct'] == 0])
        
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        avg_win = df[df['profit_pct'] > 0]['profit_pct'].mean() if winning_trades > 0 else 0
        avg_loss = df[df['profit_pct'] < 0]['profit_pct'].mean() if losing_trades > 0 else 0
        
        total_profit = df['profit_pct'].sum()
        avg_profit = df['profit_pct'].mean()
        
        print(f"\n总交易次数: {total_trades}")
        print(f"盈利交易: {winning_trades} ({win_rate:.1f}%)")
        print(f"亏损交易: {losing_trades} ({(losing_trades/total_trades)*100:.1f}%)")
        print(f"盈亏平衡: {breakeven_trades}")
        
        print(f"\n平均盈利: +{avg_win:.2f}%")
        print(f"平均亏损: {avg_loss:.2f}%")
        print(f"盈亏比: {abs(avg_win/avg_loss):.2f}" if avg_loss != 0 else "盈亏比: N/A")
        
        print(f"\n总收益: {total_profit:.2f}%")
        print(f"平均每笔: {avg_profit:.2f}%")
        
        # 计算盈利因子
        total_wins = df[df['profit_pct'] > 0]['profit_pct'].sum()
        total_losses = abs(df[df['profit_pct'] < 0]['profit_pct'].sum())
        profit_factor = total_wins / total_losses if total_losses != 0 else float('inf')
        print(f"盈利因子: {profit_factor:.2f}")
        
        # 最大回撤和最大盈利
        max_win = df['profit_pct'].max()
        max_loss = df['profit_pct'].min()
        print(f"\n最大盈利: +{max_win:.2f}%")
        print(f"最大亏损: {max_loss:.2f}%")
        
        print("\n" + "="*80)
        print("退出原因分析")
        print("="*80)
        
        # 按退出原因分组
        reason_stats = df.groupby('exit_reason').agg({
            'profit_pct': ['count', 'mean', 'sum']
        }).round(2)
        print("\n", reason_stats)
        
        print("\n按退出原因分类胜率:")
        for reason in df['exit_reason'].unique():
            reason_df = df[df['exit_reason'] == reason]
            reason_wins = len(reason_df[reason_df['profit_pct'] > 0])
            reason_total = len(reason_df)
            reason_winrate = reason_wins / reason_total * 100 if reason_total > 0 else 0
            reason_avg = reason_df['profit_pct'].mean()
            print(f"{reason:20s}: {reason_wins}/{reason_total} = {reason_winrate:5.1f}% 胜率, 平均: {reason_avg:+.2f}%")
        
        print("\n" + "="*80)
        print("持仓时长分析")
        print("="*80)
        
        # 持仓时长分组
        df['duration_group'] = pd.cut(df['duration'], 
                                       bins=[0, 2, 5, 10, 24, float('inf')], 
                                       labels=['极短(≤2h)', '短期(3-5h)', '中期(6-10h)', '长期(11-24h)', '超长(>24h)'])
        
        duration_stats = df.groupby('duration_group', observed=False).agg({
            'profit_pct': ['count', 'mean', 'sum']
        }).round(2)
        print("\n", duration_stats)
        
        print("\n各时长段胜率:")
        for group in ['极短(≤2h)', '短期(3-5h)', '中期(6-10h)', '长期(11-24h)', '超长(>24h)']:
            group_df = df[df['duration_group'] == group]
            if len(group_df) > 0:
                group_wins = len(group_df[group_df['profit_pct'] > 0])
                group_total = len(group_df)
                group_winrate = group_wins / group_total * 100 if group_total > 0 else 0
                group_avg = group_df['profit_pct'].mean()
                print(f"{group:15s}: {group_wins}/{group_total} = {group_winrate:5.1f}% 胜率, 平均: {group_avg:+.2f}%")
        
        print("\n" + "="*80)
        print("时间分布分析")
        print("="*80)
        
        # 按月份统计
        df['month'] = df['open_date'].dt.to_period('M')
        monthly_stats = df.groupby('month').agg({
            'profit_pct': ['count', 'sum', 'mean']
        }).round(2)
        print("\n月度统计:")
        print(monthly_stats)
        
        # 按星期统计
        df['weekday'] = df['open_date'].dt.day_name()
        weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        df['weekday'] = pd.Categorical(df['weekday'], categories=weekday_order, ordered=True)
        
        print("\n星期分布:")
        weekday_stats = df.groupby('weekday', observed=False).agg({
            'profit_pct': ['count', 'mean']
        }).round(2)
        print(weekday_stats)
        
        print("\n" + "="*80)
        print("关键发现")
        print("="*80)
        
        # 自动分析问题
        issues = []
        strengths = []
        
        if win_rate < 40:
            issues.append(f"❌ 胜率过低 ({win_rate:.1f}%)")
        elif win_rate > 50:
            strengths.append(f"✅ 胜率良好 ({win_rate:.1f}%)")
        
        # 分析止损交易
        stop_loss_trades = df[df['exit_reason'].str.contains('stop', case=False, na=False)]
        if len(stop_loss_trades) > 0:
            stop_loss_rate = len(stop_loss_trades) / total_trades * 100
            stop_loss_wins = len(stop_loss_trades[stop_loss_trades['profit_pct'] > 0])
            stop_loss_winrate = stop_loss_wins / len(stop_loss_trades) * 100 if len(stop_loss_trades) > 0 else 0
            
            if stop_loss_rate > 30:
                issues.append(f"❌ 止损率过高 ({stop_loss_rate:.1f}%, {len(stop_loss_trades)}/{total_trades}笔)")
            if stop_loss_winrate == 0:
                issues.append(f"❌ 止损交易全部亏损 ({len(stop_loss_trades)}笔)")
        
        # 分析持仓时长
        short_trades = df[df['duration'] <= 2]
        if len(short_trades) > 0:
            short_winrate = len(short_trades[short_trades['profit_pct'] > 0]) / len(short_trades) * 100
            if short_winrate < 30:
                issues.append(f"❌ 极短期交易胜率低 ({short_winrate:.1f}%, {len(short_trades)}笔)")
        
        long_trades = df[df['duration'] > 10]
        if len(long_trades) > 0:
            long_winrate = len(long_trades[long_trades['profit_pct'] > 0]) / len(long_trades) * 100
            if long_winrate > 60:
                strengths.append(f"✅ 长期交易胜率高 ({long_winrate:.1f}%, {len(long_trades)}笔)")
        
        # 盈亏比分析
        if abs(avg_win/avg_loss) > 2 if avg_loss != 0 else False:
            strengths.append(f"✅ 盈亏比优秀 ({abs(avg_win/avg_loss):.2f})")
        
        # 盈利因子分析
        if profit_factor > 1.5:
            strengths.append(f"✅ 盈利因子良好 ({profit_factor:.2f})")
        elif profit_factor < 1.0:
            issues.append(f"❌ 盈利因子低于1 ({profit_factor:.2f})")
        
        print("\n发现的问题:")
        if issues:
            for issue in issues:
                print(f"  {issue}")
        else:
            print("  无明显问题")
        
        print("\n优势:")
        if strengths:
            for strength in strengths:
                print(f"  {strength}")
        else:
            print("  暂无明显优势")
        
        print("\n" + "="*80)
        print("建议")
        print("="*80)
        
        recommendations = []
        
        if win_rate < 40:
            recommendations.append("• 考虑增加更严格的入场过滤条件")
            recommendations.append("• 检查是否在震荡市或假突破时入场")
        
        if len(stop_loss_trades) / total_trades > 0.3:
            recommendations.append("• 止损率过高，需要优化入场时机")
            recommendations.append("• 考虑增加趋势强度确认（如ADX指标）")
            recommendations.append("• 考虑增加成交量确认")
        
        if len(short_trades) > 0 and short_winrate < 30:
            recommendations.append("• 极短期交易质量差，考虑增加最小持仓时间要求")
            recommendations.append("• 或增加价格动量确认")
        
        if profit_factor > 1.5 and win_rate < 40:
            recommendations.append("• 盈亏比很好但胜率低，提高胜率可显著提升整体盈利")
            recommendations.append("• 重点优化入场条件，而非调整止损/止盈")
        
        if recommendations:
            for rec in recommendations:
                print(rec)
        else:
            print("策略表现良好，继续保持！")
        
        print("\n" + "="*80)
        
        # 导出详细数据
        output_file = csv_file.replace('.csv', '_analysis.csv')
        df_export = df[['open_date', 'close_date', 'duration', 'profit_pct', 'exit_reason', 'duration_group']].copy()
        df_export = df_export.sort_values('open_date')
        df_export.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n详细分析数据已导出到: {output_file}")
        
    except FileNotFoundError:
        print(f"\n错误：找不到文件 {csv_file}")
        print("\n请确保文件路径正确")
    except Exception as e:
        print(f"\n错误：{e}")
        import traceback
        traceback.print_exc()

def extract_trades_from_json(json_file):
    """从JSON文件中提取交易数据并转换为CSV格式"""
    import json
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 查找交易数据
        trades = []
        
        # 尝试多种可能的数据结构
        if isinstance(data, list):
            trades = data
        elif isinstance(data, dict):
            # meta.json的结构可能有多个策略结果
            for strategy_name, strategy_data in data.items():
                if isinstance(strategy_data, dict):
                    if 'trades' in strategy_data:
                        trades.extend(strategy_data['trades'])
                    elif 'results' in strategy_data:
                        trades.extend(strategy_data['results'])
        
        if not trades:
            print(f"\n错误：在 {json_file} 中未找到交易数据")
            print("提示：请使用 --export trades 参数重新运行回测")
            return None
        
        # 转换为DataFrame
        df = pd.DataFrame(trades)
        
        # 确保必需的列存在
        required_cols = ['open_date', 'close_date', 'profit_ratio', 'exit_reason']
        
        # 尝试映射可能的列名
        column_mapping = {
            'open_time': 'open_date',
            'close_time': 'close_date',
            'profit_abs': 'profit_ratio',
            'sell_reason': 'exit_reason',
            'close_reason': 'exit_reason',
        }
        
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns and new_col not in df.columns:
                df[new_col] = df[old_col]
        
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            print(f"\n警告：缺少必需列 {missing}")
            print(f"可用列: {df.columns.tolist()}")
            return None
        
        # 保存为临时CSV
        temp_csv = json_file.replace('.meta.json', '_trades_temp.csv').replace('.json', '_trades_temp.csv')
        df.to_csv(temp_csv, index=False)
        print(f"已从 {json_file} 提取交易数据 ({len(trades)} 笔)")
        
        return temp_csv
        
    except Exception as e:
        print(f"\n错误：无法读取 {json_file}: {e}")
        import traceback
        traceback.print_exc()
        return None

def extract_trades_from_zip(zip_file):
    """从ZIP文件中提取交易数据"""
    import zipfile
    import json
    import tempfile
    
    try:
        print(f"尝试从压缩文件中提取: {zip_file}")
        
        with zipfile.ZipFile(zip_file, 'r') as zf:
            # 列出ZIP中的文件
            file_list = zf.namelist()
            print(f"压缩文件包含: {file_list}")
            
            # 查找JSON文件
            json_files = [f for f in file_list if f.endswith('.json')]
            
            if not json_files:
                print("压缩文件中没有JSON文件")
                return None
            
            # 尝试每个JSON文件
            for json_filename in json_files:
                print(f"尝试读取: {json_filename}")
                with zf.open(json_filename) as f:
                    data = json.load(f)
                
                # 查找交易数据
                trades = []
                
                if isinstance(data, list):
                    trades = data
                elif isinstance(data, dict):
                    for strategy_name, strategy_data in data.items():
                        if isinstance(strategy_data, dict):
                            if 'trades' in strategy_data:
                                trades.extend(strategy_data['trades'])
                                print(f"找到 {len(strategy_data['trades'])} 笔交易")
                            elif 'results' in strategy_data:
                                trades.extend(strategy_data['results'])
                
                if trades:
                    # 找到数据，转换为CSV
                    df = pd.DataFrame(trades)
                    
                    # 列名映射
                    column_mapping = {
                        'open_time': 'open_date',
                        'close_time': 'close_date',
                        'profit_abs': 'profit_ratio',
                        'sell_reason': 'exit_reason',
                        'close_reason': 'exit_reason',
                    }
                    
                    for old_col, new_col in column_mapping.items():
                        if old_col in df.columns and new_col not in df.columns:
                            df[new_col] = df[old_col]
                    
                    # 保存临时CSV
                    temp_csv = zip_file.replace('.zip', '_trades_temp.csv')
                    df.to_csv(temp_csv, index=False)
                    print(f"已提取 {len(trades)} 笔交易数据")
                    
                    return temp_csv
            
            print("未在压缩文件中找到交易数据")
            return None
            
    except Exception as e:
        print(f"\n错误：无法读取 {zip_file}: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # 默认查找最新的backtest结果
    backtest_dir = Path("user_data/backtest_results")
    
    if len(sys.argv) > 1:
        # 使用命令行参数指定的文件
        csv_file = sys.argv[1]
        
        # 如果是 trades 导出的 JSON/CSV，或其它容器文件，先转换为CSV
        if csv_file.endswith('-trades.json') or csv_file.endswith('.json'):
            csv_file = extract_trades_from_json(csv_file)
            if not csv_file:
                sys.exit(1)
        elif csv_file.endswith('.zip'):
            csv_file = extract_trades_from_zip(csv_file)
            if not csv_file:
                sys.exit(1)
        # 若已是CSV则直接使用
    else:
        # 自动查找最新的 trades 导出文件，或从 zip/meta.json 中提取
        if backtest_dir.exists():
            # 优先查找CSV文件
            trade_files = list(backtest_dir.glob("*-trades.csv"))
            # 其次查找JSON导出
            trade_json_files = list(backtest_dir.glob("*-trades.json"))
            
            if not trade_files and not trade_json_files:
                # 如果没有CSV，尝试ZIP文件
                print("未找到 *-trades.csv 文件，尝试从其他格式提取...")
                
                # 先尝试ZIP文件
                zip_files = list(backtest_dir.glob("*.zip"))
                if zip_files:
                    latest_zip = str(max(zip_files, key=lambda p: p.stat().st_mtime))
                    print(f"找到最新的ZIP文件: {latest_zip}")
                    csv_file = extract_trades_from_zip(latest_zip)
                    
                    if csv_file:
                        # 成功提取
                        pass
                    else:
                        # ZIP中没有交易数据，尝试meta.json
                        print("\nZIP文件中没有交易数据，尝试 meta.json...")
                        meta_files = list(backtest_dir.glob("*.meta.json"))
                        if meta_files:
                            latest_meta = str(max(meta_files, key=lambda p: p.stat().st_mtime))
                            print(f"找到: {latest_meta}")
                            csv_file = extract_trades_from_json(latest_meta)
                
                else:
                    # 没有ZIP，尝试meta.json
                    meta_files = list(backtest_dir.glob("*.meta.json"))
                    if meta_files:
                        latest_meta = str(max(meta_files, key=lambda p: p.stat().st_mtime))
                        print(f"找到最新的meta.json: {latest_meta}")
                        csv_file = extract_trades_from_json(latest_meta)
                
                # 如果都失败了
                if not csv_file or csv_file is None:
                    print("\n" + "="*80)
                    print("❌ 无法提取交易数据")
                    print("="*80)
                    print("\n原因：回测结果中没有包含交易明细")
                    print("\n解决方法：使用 --export trades 参数重新运行回测")
                    print("\n命令示例：")
                    print("  python -m freqtrade backtesting \\")
                    print("    --strategy Bollinger4h1hStructureStrategy \\")
                    print("    --config user_data/config_bollinger_4h1h.json \\")
                    print("    --timerange 20241101-20241128 \\")
                    print("    --export trades")
                    print("\n" + "="*80)
                    sys.exit(1)
            else:
                # 直接使用最新的 trades 导出（CSV 优先，其次 JSON）
                latest_csv = max(trade_files, key=lambda p: p.stat().st_mtime) if trade_files else None
                latest_json = max(trade_json_files, key=lambda p: p.stat().st_mtime) if trade_json_files else None

                # 选择最近修改的一个
                candidates = []
                if latest_csv:
                    candidates.append(latest_csv)
                if latest_json:
                    candidates.append(latest_json)
                latest = max(candidates, key=lambda p: p.stat().st_mtime)

                if str(latest).endswith('.json'):
                    print(f"发现 trades JSON: {latest}")
                    csv_file = extract_trades_from_json(str(latest))
                    if not csv_file:
                        sys.exit(1)
                else:
                    csv_file = str(latest)
                    print(f"自动选择最新的回测结果: {csv_file}")
        else:
            print(f"\n错误：目录不存在 {backtest_dir}")
            sys.exit(1)
    
    analyze_trades(csv_file)

