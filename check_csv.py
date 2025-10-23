import pandas as pd

df = pd.read_csv('user_data/debug/BollingerHLH_BTC_USDT_1h_full.csv', encoding='utf-8-sig')

print("=" * 80)
print("CSV文件分析")
print("=" * 80)
print(f"总行数: {len(df)}")

print("\n4h数据非空的行数:")
print(f"  布林宽度4h非空: {df['布林宽度4h'].notna().sum()}")
print(f"  Armed持续4h非空: {df['Armed持续4h'].notna().sum()}")

if df['布林宽度4h'].notna().any():
    first_valid_idx = df['布林宽度4h'].notna().idxmax()
    print(f"\n第一个4h数据非空的行索引: {first_valid_idx}")
    print(f"时间: {df.loc[first_valid_idx, '时间']}")
    print(f"布林宽度4h: {df.loc[first_valid_idx, '布林宽度4h']}")
    print(f"Armed持续4h: {df.loc[first_valid_idx, 'Armed持续4h']}")

# 统计Armed持续4h为True的次数
armed_col = df['Armed持续4h']
print(f"\nArmed持续4h统计:")
print(f"  总计True次数: {(armed_col == True).sum()}")
print(f"  总计False次数: {(armed_col == False).sum()}")
print(f"  空值次数: {armed_col.isna().sum()}")

if (armed_col == True).sum() > 0:
    armed_rows = df[armed_col == True].head(10)
    print(f"\n前10个Armed=True的时间点:")
    for idx, row in armed_rows.iterrows():
        print(f"  {row['时间']}: 宽度={row['布林宽度4h']:.4f}, HLH={row['HLH信号']}, 入场={row['入场信号']}")
else:
    print("\n❌ 没有任何Armed=True的记录！")
    
# 检查最后100行
print("\n" + "=" * 80)
print("最后20行数据样本:")
print("=" * 80)
cols = ['时间', '收盘价', '布林宽度4h', 'Armed持续4h', 'HLH信号', '入场信号']
print(df.tail(20)[cols].to_string(index=False))


