"""检查布林带预热期的问题"""
import pandas as pd
import numpy as np
import freqtrade.vendor.qtpylib.indicators as qtpylib

print("=" * 80)
print("检查布林带预热期")
print("=" * 80)

# 读取4h数据
df_4h = pd.read_feather('user_data/data/binance/ETH_USDT-4h.feather')

print(f"\n4h数据总行数: {len(df_4h)}")
print(f"4h数据起始时间: {df_4h['date'].iloc[0]}")

# 计算布林带
bb_period = 20
bb_stdev = 2.0

bollinger_4h = qtpylib.bollinger_bands(df_4h['close'], window=bb_period, stds=bb_stdev)

print("\n" + "=" * 80)
print("前25根4h K线的布林带计算结果")
print("=" * 80)

# 创建结果DataFrame
result = pd.DataFrame({
    '序号': range(len(df_4h)),
    '时间': df_4h['date'],
    '收盘价': df_4h['close'],
    '中轨': bollinger_4h['mid'],
    '上轨': bollinger_4h['upper'],
    '下轨': bollinger_4h['lower'],
})

# 计算宽度
result['宽度'] = (result['上轨'] - result['下轨']) / result['中轨']

# 添加是否为NaN的标记
result['中轨是否NaN'] = result['中轨'].isna()
result['上轨是否NaN'] = result['上轨'].isna()
result['下轨是否NaN'] = result['下轨'].isna()

print("\n前25根4h K线的详细情况:")
print(result[['序号', '时间', '收盘价', '中轨', '上轨', '下轨', '宽度', '中轨是否NaN', '上轨是否NaN', '下轨是否NaN']].head(25).to_string(index=False))

# 统计
print("\n" + "=" * 80)
print("统计信息")
print("=" * 80)

first_valid_mid = result['中轨'].first_valid_index()
first_valid_upper = result['上轨'].first_valid_index()
first_valid_lower = result['下轨'].first_valid_index()

print(f"\n第一个非NaN的中轨: 索引 {first_valid_mid}, 时间 {result.loc[first_valid_mid, '时间'] if first_valid_mid is not None else 'N/A'}")
print(f"第一个非NaN的上轨: 索引 {first_valid_upper}, 时间 {result.loc[first_valid_upper, '时间'] if first_valid_upper is not None else 'N/A'}")
print(f"第一个非NaN的下轨: 索引 {first_valid_lower}, 时间 {result.loc[first_valid_lower, '时间'] if first_valid_lower is not None else 'N/A'}")

# 检查前4根（对应1h的前16小时）
print("\n" + "=" * 80)
print("前4根4h K线（对应Excel前16行1h数据）")
print("=" * 80)

for i in range(4):
    row = result.iloc[i]
    print(f"\n第{i}根4h K线:")
    print(f"  时间: {row['时间']}")
    print(f"  收盘价: {row['收盘价']:.2f}")
    print(f"  中轨: {row['中轨']}")
    print(f"  上轨: {row['上轨']}")
    print(f"  下轨: {row['下轨']}")
    print(f"  宽度: {row['宽度']}")

print("\n" + "=" * 80)
print("结论")
print("=" * 80)
print("\n如果前几根的中轨有值但上下轨是NaN，说明:")
print("  1. qtpylib.bollinger_bands 对中轨和上下轨使用了不同的min_periods")
print("  2. 中轨可能在数据不足20根时就开始计算（expanding mean）")
print("  3. 上下轨需要足够的数据才能计算标准差，所以前面是NaN")
print("  4. 这导致合并到1h数据后，前几行没有完整的布林带信息")





