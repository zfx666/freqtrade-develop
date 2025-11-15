# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these libs ---
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime, timedelta, timezone
from pathlib import Path
import talib.abstract as ta
from freqtrade.strategy import (BooleanParameter, CategoricalParameter,
                                DecimalParameter, IStrategy, IntParameter, informative, merge_informative_pair)
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.persistence import Trade
from typing import Optional, Union
import logging

logger = logging.getLogger(__name__)


class Bollinger4h1hStructureStrategy(IStrategy):
    """
    4小时布林带扩张 + 1小时结构确认策略（精确版 + 均线趋势过滤）

    策略逻辑：
    0. 【新增】趋势过滤：1h收盘价 > N小时均线（默认20小时，可配置，确保在上升趋势中交易）
    1. 4h布林带宽度≤5.5%（缩口）- 使用4h实时数据
    2. 实时价格突破布林上轨（强势信号）- 使用high判断
    3. 从4h周期起始点开始合并1h K线，检测HLH形态
    4. 入场：Armed状态下首个HLH信号触发
    5. Armed周期管理：
       - 开始：价格>均线 + 缩口 + 突破上轨
       - 结束：跌破下轨 或 硬止损-2%（基于真实入场价） 或 结构转弱（>2%）
       - 每个Armed周期只允许一次入场
    6. 止损：2%硬止损（框架层 + 指标层双重检测）
    7. 出场：跌破下轨或结构转弱或硬止损

    修改说明：
    - 添加N小时均线（默认20小时，可配置为10/30/40/50/100等）作为前置趋势过滤器
    - 只有在收盘价高于均线时才允许触发Armed状态
    - 避免在下跌趋势中逆势做多
    - 均线周期可通过ma_period参数灵活调整

    """

    INTERFACE_VERSION = 3

    # 基础设置
    timeframe = '1h'
    startup_candle_count: int = 250  # 增加到1600以支持最大1500小时均线

    # 交易时机设置
    process_only_new_candles = True

    # 使用exit信号
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # 可配置参数
    # 布林带参数（应用于4h数据）
    bb_period = IntParameter(10, 50, default=20, space="buy", optimize=True)
    bb_stdev = DecimalParameter(1.5, 3.0, default=2.0, space="buy", optimize=True)

    # 均线参数（小时K线级别，可调整为5/20/50/100/200/500/1000/1500等）
    ma_period = IntParameter(5, 1500, default=200, space="buy", optimize=True)

    # 宽度阈值固定为5.5%
    BB_WIDTH_THRESHOLD = 0.055  # 5.5%
    # 结构转弱阈值（0.02 表示 2%）
    STRUCT_WEAK_PCT = 0.02

    # 仓位参数
    stake_ratio = DecimalParameter(0.1, 1.0, default=1.0, space="buy", optimize=True)

    # 全局止损：设置为2%的实际止损值
    stoploss = -0.02  # 2%止损

    # 不使用roi，由策略控制出场
    minimal_roi = {"0": 100}

    # 启用追踪止损（可选，如果想要盈利后收紧止损可以启用）
    # trailing_stop = True
    # trailing_stop_positive = 0.005  # 盈利0.5%后启动追踪
    # trailing_stop_positive_offset = 0.01  # 盈利1%后追踪
    # trailing_only_offset_is_reached = True

    # 内部状态跟踪
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.entry_price = None
        # 调试输出控制
        self.enable_debug_dump: bool = True
        self.debug_dump_rows: int = 300
        # 回测逐小时明细打印/导出
        self.enable_full_hourly_trace: bool = True
        self.full_trace_log_rows: int = 200
        # 交易记录跟踪
        self.trades_history: list = []  # 存储所有交易记录
        # Armed状态追踪：记录每次armed触发的4h周期起始时间
        self.armed_4h_start_hour = {}  # {pair: hour_of_day}
        self.full_trace_columns: list[str] = [
            # 1h基础数据
            'date', 'open', 'high', 'low', 'close', 'volume',
            # 均线数据
            'ma20', 'is_above_ma20',
            # 4h布林带数据
            'bb_upper_4h', 'bb_middle_4h', 'bb_lower_4h', 'bb_width_4h',
            # 实时条件判断
            'is_width_ok', 'is_breakout', 'is_below_lower', 'is_armed', 'armed_active',
            # 1h结构
            'structure_high', 'structure_low', 'is_new_structure', 'hlh_signal',
            # 入场信号
            'debug_entry_eval', 'enter_long',
            # 4h周期信息
            '4h_period_start'
        ]

    @informative('4h', ffill=True)
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算4h布林带指标
        注意：数据会自动向前偏移1个4h周期，避免未来函数
        例如：08:00使用的是04:00-08:00的4h数据（已完成），而不是08:00-12:00的（未完成）
        """
        # 基于4h收盘价计算布林带
        bollinger = qtpylib.bollinger_bands(
            dataframe['close'],
            window=self.bb_period.value,
            stds=self.bb_stdev.value
        )
        dataframe['bb_upper'] = bollinger['upper']
        dataframe['bb_middle'] = bollinger['mid']
        dataframe['bb_lower'] = bollinger['lower']

        # 宽度计算 (上轨-下轨)/中轨
        dataframe['bb_width'] = (
                (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_middle']
        )

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """填充1h指标，使用4h布林带数据"""
        # 4h布林带数据会自动通过@informative装饰器合并到dataframe
        # 字段名为：bb_upper_4h, bb_middle_4h, bb_lower_4h, bb_width_4h

        # 诊断：打印前20行4h数据，检查对齐情况
        if len(dataframe) > 0:
            logger.info("=" * 80)
            logger.info("4h数据对齐检查（前20行）:")
            for i in range(min(20, len(dataframe))):
                date = dataframe['date'].iloc[i]
                bb_mid = dataframe.get('bb_middle_4h', pd.Series([None] * len(dataframe))).iloc[i]
                logger.info(f"  {date} → bb_middle_4h={bb_mid}")
            logger.info("=" * 80)

        # 关键修复：先shift(1)再ffill
        # 原因：freqtrade的merge_asof会导致4h数据提前1小时出现
        # 例如：03:00就能看到04:00的4h数据，需要向后推1小时
        # shift(1)后：04:00-07:00共享同一个4h值
        if 'bb_upper_4h' in dataframe.columns:
            dataframe['bb_upper_4h'] = dataframe['bb_upper_4h'].shift(1).ffill()
        if 'bb_middle_4h' in dataframe.columns:
            dataframe['bb_middle_4h'] = dataframe['bb_middle_4h'].shift(1).ffill()
        if 'bb_lower_4h' in dataframe.columns:
            dataframe['bb_lower_4h'] = dataframe['bb_lower_4h'].shift(1).ffill()
        if 'bb_width_4h' in dataframe.columns:
            dataframe['bb_width_4h'] = dataframe['bb_width_4h'].shift(1).ffill()

        # 计算当前1h K线所属的4h周期起始时间（用于结构合并）
        # 4h周期为：0-4, 4-8, 8-12, 12-16, 16-20, 20-24
        # 注意：这是"所属周期"，不是"实际使用的4h数据"
        # 例如：08:00属于8-12周期，但实际使用的是4-8周期的已完成4h数据
        dataframe['4h_period_start'] = dataframe['date'].apply(
            lambda x: x.hour // 4 * 4 if hasattr(x, 'hour') else 0
        )

        # 计算MA（基于1h收盘价，默认100小时，可配置）
        dataframe['ma20'] = ta.SMA(dataframe['close'], timeperiod=self.ma_period.value)
        
        # 均线条件：1h收盘价 > N小时均线（趋势过滤器）
        # 关键修复：fillna(False) 处理NaN值，前N根K线没有均线，视为不满足条件
        dataframe['is_above_ma20'] = (dataframe['close'] > dataframe['ma20']).fillna(False)

        # 实时判断条件（使用4h布林带）
        # 缩口：4h宽度 <= 5.5%
        dataframe['is_width_ok'] = dataframe['bb_width_4h'] <= self.BB_WIDTH_THRESHOLD
        # 实时突破上轨：1h的high > 4h上轨（模拟盘中实时突破）
        dataframe['is_breakout'] = dataframe['high'] > dataframe['bb_upper_4h']
        # 跌破下轨：1h收盘价 <= 4h下轨
        dataframe['is_below_lower'] = dataframe['close'] <= dataframe['bb_lower_4h']

        # Armed触发条件：均线条件 AND 缩口 AND 突破上轨
        # 修改说明：添加N小时均线（默认100h，可配置）作为前置趋势过滤器，确保只在上升趋势中交易
        # 关键：均线条件已经处理了NaN，前N根K线自动不满足Armed条件
        dataframe['is_armed'] = (
                dataframe['is_above_ma20'] &
                dataframe['is_width_ok'] & 
                dataframe['is_breakout']
        )
        
        # 🔍 调试验证：打印关键统计
        ma_count = int(dataframe['is_above_ma20'].sum())
        width_breakout = dataframe['is_width_ok'] & dataframe['is_breakout']
        width_breakout_count = int(width_breakout.sum())
        armed_count_check = int(dataframe['is_armed'].sum())
        filtered_by_ma_check = width_breakout & (~dataframe['is_above_ma20'])
        filtered_count_check = int(filtered_by_ma_check.sum())
        
        logger.warning("=" * 80)
        logger.warning(f"🔍 [{metadata['pair']}] 均线过滤验证（周期={self.ma_period.value}小时）:")
        logger.warning(f"  - 价格>均线: {ma_count} 次")
        logger.warning(f"  - 缩口+突破(无均线): {width_breakout_count} 次")
        logger.warning(f"  - 被均线过滤: {filtered_count_check} 次")
        logger.warning(f"  - Armed触发(有均线): {armed_count_check} 次")
        logger.warning(f"  - 过滤率: {filtered_count_check / width_breakout_count * 100 if width_breakout_count > 0 else 0:.1f}%")
        logger.warning("=" * 80)

        # 生成粘性 Armed 状态机：一旦Armed出现，持续到跌破下轨
        # 状态转换逻辑：
        # - 触发条件：is_armed = True (价格>均线 AND 缩口 AND 突破上轨)
        # - 重置条件：is_below_lower = True (跌破下轨)
        armed_active = pd.Series(False, index=dataframe.index)
        current_state = False
        armed_trigger_idx = None  # 记录armed触发时的索引

        for i in range(len(dataframe)):
            # 获取当前行的状态
            is_armed = bool(dataframe['is_armed'].iloc[i]) if pd.notna(dataframe['is_armed'].iloc[i]) else False
            is_below = bool(dataframe['is_below_lower'].iloc[i]) if pd.notna(
                dataframe['is_below_lower'].iloc[i]) else False

            # 状态转换逻辑
            if is_below:
                if current_state:  # 只在Armed状态下才记录重置
                    logger.info(f"[{metadata['pair']}] Armed重置（跌破下轨）@ {dataframe['date'].iloc[i]}")
                current_state = False  # 重置条件：跌破下轨
                armed_trigger_idx = None
            elif is_armed and not current_state:
                current_state = True  # Armed触发，进入Armed状态
                armed_trigger_idx = i
                # 打印详细的Armed触发信息
                _close = dataframe['close'].iloc[i]
                _ma = dataframe['ma20'].iloc[i]
                _above_ma = dataframe['is_above_ma20'].iloc[i]
                _width = dataframe['bb_width_4h'].iloc[i]
                _upper = dataframe['bb_upper_4h'].iloc[i]
                _high = dataframe['high'].iloc[i]
                logger.info(f"[{metadata['pair']}] Armed触发 @ {dataframe['date'].iloc[i]} (索引{i})")
                logger.info(f"  ✅ 收盘价={_close:.2f}, {self.ma_period.value}h均线={_ma:.2f}, 价格>均线={_above_ma}")
                logger.info(f"  ✅ 4h布林宽度={_width:.3%}, 最高价={_high:.2f}, 上轨={_upper:.2f}")
            # 否则保持当前状态

            armed_active.iloc[i] = current_state

        dataframe['armed_active'] = armed_active

        # 基于armed_active计算1h结构（从4h周期起始点开始）
        dataframe = self._calculate_1h_structure(dataframe, metadata)

        # 打印最新的布林带计算结果（4h数据）
        if len(dataframe) > 0:
            _last = dataframe.iloc[-1]
            _up = float(_last.get('bb_upper_4h', np.nan))
            _lo = float(_last.get('bb_lower_4h', np.nan))
            _mi = float(_last.get('bb_middle_4h', np.nan))
            _wd = float(_last.get('bb_width_4h', np.nan))
            logger.info("[BB_WIDTH_4H %s] (upper - lower) / middle", metadata.get('pair'))
            logger.info(
                "[BB_WIDTH_4H %s] upper=%.6f lower=%.6f middle=%.6f => width=%.6f (%.3f%%) [阈值=5.5%%]",
                metadata.get('pair'), _up, _lo, _mi, _wd, (_wd * 100.0 if np.isfinite(_wd) else float('nan'))
            )

        # 添加调试统计日志
        self._log_debug_stats(dataframe, metadata['pair'])

        # 在指标阶段也导出CSV，确保回测一定产生文件（即使未触发入场流程）
        if getattr(self, 'enable_debug_dump', False):
            try:
                logger.info("[CSV] Writing recent-window CSV for %s ...", metadata.get('pair'))
                self._dump_debug_trace(dataframe, metadata)
                if getattr(self, 'enable_full_hourly_trace', False):
                    self._dump_full_dataframe_trace(dataframe, metadata)
            except Exception:
                pass

        # （移除漂亮统计块调用，保持原有输出）

        return dataframe

    def _calculate_1h_structure(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算1h结构合并和HLH检测（从4h周期起始时间开始）

        新逻辑（基于pending状态）：
        1. Armed触发时，找到4h周期起始时间
        2. 初始化 pending = 第一根K线（不立即产出结构线）
        3. 从第二根开始扫描：
           - 比较 pending 与当前K线
           - 如果包含（任意方向）：只保持 pending，不更新高低点
           - 如果非包含：在"上一根"时刻产出 pending 为结构线，然后 pending = 当前K线
           - 每次产出结构线时做 HLH 检测
        4. 扫描结束时：
           - 用 pending 与最后一根已确认结构线比较
           - 如果包含：不新增（采用前一根）
           - 如果不包含：在当前时刻产出 pending 为新结构线
        """
        dataframe['structure_high'] = 0.0
        dataframe['structure_low'] = 0.0
        dataframe['hlh_signal'] = False
        dataframe['is_new_structure'] = False

        armed_start_idx = None
        armed_4h_start_hour = None
        structure_start_idx = None
        structure_list = []  # 已确认的结构线列表
        pending = None  # 当前未确认的结构段: {'high': h, 'low': l, 'start_idx': i, 'start_time': t}
        hlh_triggered = False
        entry_idx = None
        entry_price = None
        prev_struct_low = None
        armed_end_points = []

        def produce_structure(idx, high, low):
            """产出一根结构线并执行HLH检测"""
            nonlocal hlh_triggered, entry_idx, entry_price, prev_struct_low
            
            structure_list.append({
                'idx': idx,
                'high': high,
                'low': low,
                'time': dataframe['date'].iloc[idx] if 'date' in dataframe.columns else None
            })
            
            # 写入DataFrame
            dataframe.loc[dataframe.index[idx], 'structure_high'] = high
            dataframe.loc[dataframe.index[idx], 'structure_low'] = low
            dataframe.loc[dataframe.index[idx], 'is_new_structure'] = True
            
            # 更新上一个结构低点
            if len(structure_list) >= 2:
                prev_struct_low = structure_list[-2]['low']
            
            # HLH 检测（仅在产出时）
            if len(structure_list) >= 3 and not hlh_triggered:
                hlh_found = False
                hlh_window_start = 0
                
                for window_start in range(len(structure_list) - 2):
                    s1 = structure_list[window_start]
                    s2 = structure_list[window_start + 1]
                    s3 = structure_list[window_start + 2]
                    
                    if self._check_hlh_pattern(s1, s2, s3):
                        hlh_found = True
                        hlh_window_start = window_start
                        break
                
                if hlh_found:
                    dataframe.loc[dataframe.index[idx], 'hlh_signal'] = True
                    hlh_triggered = True
                    entry_idx = idx
                    entry_price = dataframe['close'].iloc[idx]
                    s1 = structure_list[hlh_window_start]
                    s2 = structure_list[hlh_window_start + 1]
                    s3 = structure_list[hlh_window_start + 2]
                    logger.info(
                        f"[1h结构] 检测到HLH @ 索引{idx}, "
                        f"结构线数={len(structure_list)}, "
                        f"HLH窗口=[{hlh_window_start},{hlh_window_start + 2}], "
                        f"s1=[{s1['high']:.2f},{s1['low']:.2f}], "
                        f"s2=[{s2['high']:.2f},{s2['low']:.2f}], "
                        f"s3=[{s3['high']:.2f},{s3['low']:.2f}], "
                        f"入场价={entry_price:.2f}"
                    )

        for i in range(len(dataframe)):
            is_armed_now = bool(dataframe['armed_active'].iloc[i]) if 'armed_active' in dataframe.columns else False

            if is_armed_now:
                if armed_start_idx is None:
                    # Armed刚触发
                    armed_start_idx = i
                    hlh_triggered = False
                    entry_idx = None
                    entry_price = None
                    prev_struct_low = None
                    structure_list = []
                    pending = None

                    # 找到4h周期起始时间
                    current_4h_start = dataframe['4h_period_start'].iloc[i]
                    armed_4h_start_hour = current_4h_start

                    # 找到该4h周期的起始索引
                    structure_start_idx = i
                    for j in range(i, -1, -1):
                        if dataframe['4h_period_start'].iloc[j] == current_4h_start:
                            structure_start_idx = j
                        else:
                            break

                    logger.info(
                        f"[1h结构] Armed触发 @ 索引{i}, 4h周期起始={current_4h_start}h, 合并起始索引={structure_start_idx}")

                    # 初始化 pending 为第一根K线
                    pending = {
                        'high': dataframe['high'].iloc[structure_start_idx],
                        'low': dataframe['low'].iloc[structure_start_idx],
                        'start_idx': structure_start_idx
                    }

                    # 如果起始索引不是当前索引，需要处理中间的K线
                    if structure_start_idx < i:
                        for j in range(structure_start_idx + 1, i + 1):
                            curr_high = dataframe['high'].iloc[j]
                            curr_low = dataframe['low'].iloc[j]
                            ph, pl = pending['high'], pending['low']
                            
                            # 判断包含关系
                            prev_contains_curr = (ph >= curr_high and pl <= curr_low)
                            curr_contains_prev = (ph <= curr_high and pl >= curr_low)

                            if prev_contains_curr:
                                # 前包含后：保持pending不变（前一根波动范围更大）
                                continue
                            elif curr_contains_prev:
                                # 后包含前：更新pending为当前K线（当前根波动范围更大）
                                pending = {'high': curr_high, 'low': curr_low, 'start_idx': j}
                                continue
                            else:
                                # 非包含：在上一根时刻产出 pending
                                prev_idx = j - 1
                                produce_structure(prev_idx, ph, pl)
                                # 重置 pending 为当前K线
                                pending = {'high': curr_high, 'low': curr_low, 'start_idx': j}

                    logger.info(f"[1h结构] 初始化完成，索引{structure_start_idx}到{i}，已确认结构线={len(structure_list)}根")
                else:
                    # Armed持续，处理当前K线
                    if pending is not None:
                        curr_high = dataframe['high'].iloc[i]
                        curr_low = dataframe['low'].iloc[i]
                        ph, pl = pending['high'], pending['low']

                        # 判断包含关系
                        prev_contains_curr = (ph >= curr_high and pl <= curr_low)
                        curr_contains_prev = (ph <= curr_high and pl >= curr_low)

                        if prev_contains_curr:
                            # 前包含后：保持pending不变（前一根波动范围更大）
                            pass
                        elif curr_contains_prev:
                            # 后包含前：更新pending为当前K线（当前根波动范围更大）
                            pending = {'high': curr_high, 'low': curr_low, 'start_idx': i}
                        else:
                            # 非包含：在上一根时刻产出 pending
                            prev_idx = i - 1
                            produce_structure(prev_idx, ph, pl)
                            # 重置 pending 为当前K线
                            pending = {'high': curr_high, 'low': curr_low, 'start_idx': i}

                        # 检测Armed周期结束条件（在入场后才开始检测）
                        if entry_idx is not None and entry_price is not None:
                            armed_should_end = False
                            end_reason = None

                            # 条件1：跌破下轨
                            is_below = bool(dataframe['is_below_lower'].iloc[i]) if pd.notna(
                                dataframe['is_below_lower'].iloc[i]) else False
                            if is_below:
                                armed_should_end = True
                                end_reason = "跌破下轨"

                            # 条件2：硬止损-1%
                            current_low = dataframe['low'].iloc[i]
                            sl_level = entry_price * (1 - 0.01)
                            if current_low <= sl_level:
                                armed_should_end = True
                                end_reason = "硬止损-1%"

                            # 条件3：结构转弱
                            if prev_struct_low is not None and len(structure_list) > 0:
                                curr_struct_low = structure_list[-1]['low']
                                if curr_struct_low < prev_struct_low:
                                    drop_pct = (prev_struct_low - curr_struct_low) / prev_struct_low
                                    if drop_pct >= self.STRUCT_WEAK_PCT:
                                        armed_should_end = True
                                        end_reason = "结构转弱"

                            if armed_should_end:
                                # 扫描结束前：处理最后的 pending
                                if pending is not None and len(structure_list) > 0:
                                    last_struct = structure_list[-1]
                                    ph, pl = pending['high'], pending['low']
                                    lh, ll = last_struct['high'], last_struct['low']
                                    
                                    # 与最后一根已确认结构线比较
                                    prev_contains_curr = (lh >= ph and ll <= pl)
                                    curr_contains_prev = (lh <= ph and ll >= pl)
                                    
                                    if not (prev_contains_curr or curr_contains_prev):
                                        # 不包含：在当前时刻产出 pending
                                        produce_structure(i, ph, pl)
                                
                                logger.info(
                                    f"[Armed周期] 周期结束 @ 索引{i}, 原因={end_reason}, 入场价={entry_price:.2f}, 当前价={dataframe['close'].iloc[i]:.2f}")
                                armed_end_points.append((i, end_reason))
                                armed_start_idx = None
                                armed_4h_start_hour = None
                                structure_start_idx = None
                                structure_list = []
                                pending = None
                                hlh_triggered = False
                                entry_idx = None
                                entry_price = None
                                prev_struct_low = None
            else:
                # Armed失效
                if armed_start_idx is not None:
                    # 扫描结束前：处理最后的 pending
                    if pending is not None:
                        if len(structure_list) == 0:
                            # 没有已确认结构，直接产出 pending
                            produce_structure(i - 1, pending['high'], pending['low'])
                        else:
                            # 与最后一根已确认结构线比较
                            last_struct = structure_list[-1]
                            ph, pl = pending['high'], pending['low']
                            lh, ll = last_struct['high'], last_struct['low']
                            
                            prev_contains_curr = (lh >= ph and ll <= pl)
                            curr_contains_prev = (lh <= ph and ll >= pl)
                            
                            if not (prev_contains_curr or curr_contains_prev):
                                # 不包含：在上一根时刻产出 pending
                                produce_structure(i - 1, ph, pl)
                    
                    logger.info(f"[1h结构] Armed失效 @ 索引{i}, 重置累积")
                    armed_start_idx = None
                    armed_4h_start_hour = None
                    structure_start_idx = None
                    structure_list = []
                    pending = None
                    hlh_triggered = False

        # 后处理：处理Armed周期结束点
        if armed_end_points:
            logger.info(f"[Armed周期] 共检测到{len(armed_end_points)}个结束点")
            first_end_idx, first_reason = armed_end_points[0]
            logger.info(f"[Armed周期] 从索引{first_end_idx}开始清理，原因={first_reason}")

            for j in range(first_end_idx + 1, len(dataframe)):
                is_new_armed = bool(dataframe['is_armed'].iloc[j]) if pd.notna(dataframe['is_armed'].iloc[j]) else False
                if is_new_armed:
                    logger.info(f"[Armed周期] 索引{j}检测到新周期开始，停止清空")
                    break
                if dataframe['armed_active'].iloc[j]:
                    dataframe.loc[dataframe.index[j], 'armed_active'] = False

        # 1h结构调试日志
        self._log_structure_stats(dataframe)
        return dataframe

    def _check_hlh_pattern(self, s1: dict, s2: dict, s3: dict) -> bool:
        """
        检查3根结构线是否形成HLH模式（基于相对关系）

        HLH模式定义（做多信号）：
        - 高-低-高: s2是低点（比s1和s3都低），形成底部反转

        判定标准：
        - s2的高点 < s1的高点 AND s2的低点 < s1的低点
        - s2的高点 < s3的高点 AND s2的低点 < s3的低点

        注意：不接受LHL（低-高-低）模式，因为那是做空信号

        Args:
            s1: 第1根结构线 {'high': float, 'low': float}
            s2: 第2根结构线
            s3: 第3根结构线

        Returns:
            True if HLH pattern detected
        """
        # 高-低-高模式：s2是低点（形成底部）
        # s2相对s1：高点和低点都更低
        condition1 = s2['high'] < s1['high'] and s2['low'] < s1['low']

        # s2相对s3：高点和低点都更低
        condition2 = s2['high'] < s3['high'] and s2['low'] < s3['low']

        # 只有两个条件都满足，才是HLH模式
        hlh_pattern = condition1 and condition2

        return hlh_pattern

    def _process_accumulated_structure(self, accumulated_data: DataFrame) -> dict:
        """
        处理累积的1h数据，进行结构合并和HLH检测

        Args:
            accumulated_data: Armed触发后累积的1h数据

        Returns:
            dict: {
                'highs': 合成后的高点数组,
                'lows': 合成后的低点数组,
                'types': 结构类型数组,
                'hlh_detected': 是否检测到HLH
            }
        """
        highs = accumulated_data['high'].values
        lows = accumulated_data['low'].values
        length = len(accumulated_data)

        structure_highs = np.zeros(length)
        structure_lows = np.zeros(length)
        structure_types = np.zeros(length)

        # 初始化
        self._initialize_structure_arrays(highs, lows, length, structure_highs, structure_lows, structure_types)

        # 逐根合并
        for i in range(2, length):
            self._merge_single_candle(i, highs, lows, structure_highs, structure_lows, structure_types)

        # HLH检测
        hlh_detected = False
        if length >= 3:
            # 检查最新的3个结构是否构成HLH
            for i in range(2, length):
                if structure_types[i - 2] == 1 and structure_types[i - 1] == -1 and structure_types[i] == 1:
                    hlh_detected = True
                    break

        return {
            'highs': structure_highs,
            'lows': structure_lows,
            'types': structure_types,
            'hlh_detected': hlh_detected
        }

    def _get_group_keys(self, dataframe: DataFrame) -> pd.Series:
        """获取分组键（已废弃，保留以防兼容性问题）"""
        if 'date_4h' in dataframe.columns:
            return dataframe['date_4h']
        elif 'close_4h' in dataframe.columns:
            return (dataframe['close_4h'] != dataframe['close_4h'].shift()).cumsum()
        else:
            return pd.Series(0, index=dataframe.index)

    def _process_single_group(self, dataframe: DataFrame, idx) -> dict:
        """处理单个4h分组的结构计算"""
        sl = dataframe.loc[idx]
        highs = sl['high'].values
        lows = sl['low'].values
        length = len(sl)

        structure_highs = np.zeros(length)
        structure_lows = np.zeros(length)
        structure_types = np.zeros(length)
        hlh_signals = np.zeros(length, dtype=bool)

        # 初始化
        self._initialize_structure_arrays(highs, lows, length, structure_highs, structure_lows, structure_types)

        # 合并计算
        for i in range(2, length):
            self._merge_single_candle(i, highs, lows, structure_highs, structure_lows, structure_types)

        # HLH检测
        self._detect_hlh_patterns(structure_types, length, hlh_signals)

        return {
            'highs': structure_highs,
            'lows': structure_lows,
            'types': structure_types,
            'hlh_signals': hlh_signals
        }

    def _initialize_structure_arrays(self, highs, lows, length, structure_highs, structure_lows, structure_types):
        """初始化结构数组"""
        if length >= 1:
            structure_highs[0] = highs[0]
            structure_lows[0] = lows[0]
            structure_types[0] = 1

        if length >= 2:
            structure_highs[1] = highs[1]
            structure_lows[1] = lows[1]
            if highs[1] > highs[0] and lows[1] > lows[0]:
                structure_types[1] = 1
            elif highs[1] < highs[0] and lows[1] < lows[0]:
                structure_types[1] = -1
            else:
                structure_highs[1] = structure_highs[0]
                structure_lows[1] = structure_lows[0]
                structure_types[1] = structure_types[0]

    def _merge_single_candle(self, i, highs, lows, structure_highs, structure_lows, structure_types):
        """合并单个K线"""
        prev_high = structure_highs[i - 1]
        prev_low = structure_lows[i - 1]
        curr_high = highs[i]
        curr_low = lows[i]

        if self._is_contained(prev_high, prev_low, curr_high, curr_low):
            structure_highs[i] = prev_high
            structure_lows[i] = prev_low
            structure_types[i] = structure_types[i - 1]
        else:
            structure_highs[i] = curr_high
            structure_lows[i] = curr_low
            if curr_high > prev_high and curr_low > prev_low:
                structure_types[i] = 1
            elif curr_high < prev_high and curr_low < prev_low:
                structure_types[i] = -1
            else:
                structure_types[i] = structure_types[i - 1]

    def _detect_hlh_patterns(self, structure_types, length, hlh_signals):
        """检测HLH模式"""
        if length >= 3:
            for i in range(2, length):
                if structure_types[i - 2] == 1 and structure_types[i - 1] == -1 and structure_types[i] == 1:
                    hlh_signals[i] = True

    def _log_structure_stats(self, dataframe: DataFrame):
        """记录结构统计信息"""
        total_hlh = int(dataframe['hlh_signal'].sum())
        if total_hlh > 0:
            hlh_indices = dataframe.index[dataframe['hlh_signal']].tolist()
            logger.info("1h结构: 检测到 %d 个HLH信号，位置: %s", total_hlh, hlh_indices[-3:])
        else:
            high_points = int((dataframe['structure_type'] == 1).sum())
            low_points = int((dataframe['structure_type'] == -1).sum())
            logger.info("1h结构: 无HLH信号 - 高点:%d, 低点:%d, 总K线:%d", high_points, low_points, len(dataframe))

    def _is_contained(self, prev_high: float, prev_low: float,
                      curr_high: float, curr_low: float) -> tuple:
        """
        判断是否为包含关系，并返回处理方式

        Returns:
            tuple: (is_contained, contain_type, merged_high, merged_low)
            - is_contained: 是否包含
            - contain_type: 'prev_contains_curr'(前包含后) 或 'curr_contains_prev'(后包含前)
            - merged_high: 合并后的高点
            - merged_low: 合并后的低点
        """
        # 前包含后：前高 >= 当前高 AND 前低 <= 当前低
        if prev_high >= curr_high and prev_low <= curr_low:
            # 前包含后，保持前结构点不变
            return (True, 'prev_contains_curr', prev_high, prev_low)

        # 后包含前：前高 <= 当前高 AND 前低 >= 当前低
        elif prev_high <= curr_high and prev_low >= curr_low:
            # 后包含前，采用后面的高低点（修改前结构点）
            return (True, 'curr_contains_prev', curr_high, curr_low)

        # 非包含关系
        else:
            return (False, None, curr_high, curr_low)

    def _detect_hlh(self, types: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> bool:
        """检测高-低-高模式"""
        if len(types) < 3:
            return False

        # 检查模式：高(1) -> 低(-1) -> 高(1)
        if types[0] == 1 and types[1] == -1 and types[2] == 1:
            # 可选：增强条件，第三个高点要≥第一个高点
            # if highs[2] >= highs[0]:
            #     return True
            return True

        return False

    def _log_debug_stats(self, dataframe: DataFrame, pair: str) -> None:
        """输出调试统计信息"""
        if len(dataframe) == 0:
            return

        # 统计均线条件
        above_ma20_count = dataframe['is_above_ma20'].sum() if 'is_above_ma20' in dataframe.columns else 0

        # 统计实时条件（使用4h布林带）
        width_ok_count = dataframe['is_width_ok'].sum() if 'is_width_ok' in dataframe.columns else 0
        breakout_count = dataframe['is_breakout'].sum() if 'is_breakout' in dataframe.columns else 0
        armed_count = dataframe['is_armed'].sum() if 'is_armed' in dataframe.columns else 0
        armed_active_count = dataframe['armed_active'].sum() if 'armed_active' in dataframe.columns else 0

        # 统计1h条件
        hlh_count = dataframe['hlh_signal'].sum() if 'hlh_signal' in dataframe.columns else 0

        # 统计入场信号
        entry_signals = 0
        if 'armed_active' in dataframe.columns and 'hlh_signal' in dataframe.columns:
            entry_signals = (dataframe['armed_active'] & dataframe['hlh_signal']).sum()

        # 最新状态
        latest = dataframe.iloc[-1]
        latest_width_4h = latest.get('bb_width_4h', 0)
        latest_close = latest.get('close', 0)
        latest_ma20 = latest.get('ma20', 0)
        latest_above_ma20 = latest.get('is_above_ma20', False)
        latest_upper_4h = latest.get('bb_upper_4h', 0)
        latest_lower_4h = latest.get('bb_lower_4h', 0)
        latest_armed = latest.get('armed_active', False)
        latest_hlh = latest.get('hlh_signal', False)

        # 统计各条件组合
        width_and_breakout = dataframe['is_width_ok'] & dataframe['is_breakout']
        width_and_breakout_count = int(width_and_breakout.sum()) if 'is_width_ok' in dataframe.columns else 0
        
        # 统计被均线过滤掉的Armed触发次数
        filtered_by_ma = width_and_breakout & (~dataframe['is_above_ma20'])
        filtered_count = int(filtered_by_ma.sum()) if 'is_above_ma20' in dataframe.columns else 0

        logger.info("[%s] 调试统计 (总计 %d 根1h K线):", pair, len(dataframe))
        logger.info("  均线趋势条件统计:")
        logger.info("    - 收盘价>%d小时均线: %d 次", self.ma_period.value, above_ma20_count)
        logger.info("  4h布林带条件统计:")
        logger.info("    - 宽度<=5.5%% (缩口): %d 次", width_ok_count)
        logger.info("    - 实时突破上轨(high>上轨): %d 次", breakout_count)
        logger.info("    - 缩口+突破(无均线过滤): %d 次", width_and_breakout_count)
        logger.info("    - ⚠️ 被均线过滤掉: %d 次", filtered_count)
        logger.info("    - Armed触发(均线+缩口+突破): %d 次", armed_count)
        logger.info("    - Armed持续: %d 小时", armed_active_count)
        logger.info("  1h结构统计:")
        logger.info("    - HLH信号: %d 次", hlh_count)
        logger.info("  最终入场信号: %d 次", entry_signals)
        logger.info("  最新状态:")
        logger.info("    - 1h收盘价: %.2f, %d小时均线: %.2f, 在均线上方: %s", latest_close, self.ma_period.value, latest_ma20, latest_above_ma20)
        logger.info("    - 4h布林宽度: %.3f%%", latest_width_4h * 100)
        logger.info("    - 4h上轨: %.2f, 下轨: %.2f", latest_upper_4h, latest_lower_4h)
        logger.info("    - Armed: %s, HLH: %s", latest_armed, latest_hlh)

        # 如果有入场信号，显示具体时间点
        if entry_signals > 0:
            entry_mask = dataframe['armed_active'] & dataframe['hlh_signal']
            entry_times = dataframe[entry_mask].index.tolist()[-5:]  # 最近5个信号
            logger.info(f"  最近入场信号时间: {entry_times}")

        # 显示最近Armed状态的时间
        if armed_active_count > 0:
            armed_mask = dataframe['armed_active']
            armed_times = dataframe[armed_mask].index.tolist()[-3:]  # 最近3次Armed
            logger.info(f"  最近Armed持续时间: {armed_times}")

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """入场信号"""
        # 入场条件：
        # 1. Armed状态（收盘价>均线 AND 4h宽度<=5.5% AND 实时突破上轨）
        # 2. 1h出现HLH信号

        # 使用持久 Armed（armed_active）与当前行 HLH 信号
        armed_series = dataframe.get('armed_active', dataframe.get('is_armed', pd.Series(False, index=dataframe.index)))

        # 综合入场条件（移除所有安全检查）
        entry_conditions = (
                armed_series.astype(bool) &
                dataframe['hlh_signal'].astype(bool)
        )
        dataframe['debug_entry_eval'] = entry_conditions.astype(bool)

        dataframe.loc[entry_conditions, 'enter_long'] = 1

        # 详细的入场日志
        total_entry_signals = int(entry_conditions.sum())
        armed_count = int(armed_series.sum())
        hlh_count = int(dataframe['hlh_signal'].sum())

        logger.info(f"[{metadata['pair']}] 入场信号分析:")
        logger.info(f"  - 总行数: {len(dataframe)}")
        logger.info(f"  - Armed状态次数: {armed_count}")
        logger.info(f"  - HLH信号次数: {hlh_count}")
        logger.info(f"  - 最终入场信号: {total_entry_signals}")

        if total_entry_signals > 0:
            # 显示入场信号的具体时间
            entry_indices = dataframe[entry_conditions].index.tolist()
            logger.info(f"  - 入场信号时间: {entry_indices[-3:]}")  # 最近3个

        # 可选：将最近N行的关键列写入CSV，便于排查为何未触发入场
        if getattr(self, 'enable_debug_dump', False):
            try:
                self._dump_debug_trace(dataframe, metadata)
            except Exception as _:
                pass

        # 回测：打印每小时的 DataFrame 明细（限制最近N行）并导出完整CSV
        if getattr(self, 'enable_full_hourly_trace', False):
            try:
                self._log_hourly_dataframe(dataframe, metadata)
                self._dump_full_dataframe_trace(dataframe, metadata)
            except Exception as _:
                pass

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """出场信号（这里不设置，使用custom_exit）"""
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: float | None, max_stake: float,
                            leverage: float, entry_tag: str | None, side: str,
                            **kwargs) -> float:
        """自定义仓位大小"""
        # 返回账户的固定比例
        wallet_balance = self.wallets.get_total_stake_amount()
        stake_amount = wallet_balance * self.stake_ratio.value

        # 确保在最小和最大范围内
        if min_stake is not None:
            stake_amount = max(stake_amount, min_stake)
        stake_amount = min(stake_amount, max_stake)

        logger.info(f"[{pair}] 入场仓位: {stake_amount:.2f} (账户比例: {self.stake_ratio.value:.1%})")
        return stake_amount

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> str | bool | None:
        """自定义出场逻辑"""
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        if dataframe is None or len(dataframe) == 0:
            return None

        latest = dataframe.iloc[-1]

        # 记录入场价格
        if self.entry_price is None:
            self.entry_price = trade.open_rate

        # 注意：2%止损已由 stoploss = -0.02 自动处理，无需在这里判断
        # Freqtrade 会自动在价格跌破2%时触发硬止损

        exit_reason = None

        # 条件1：结构转弱（使用结构低点而非原始K线低点）
        # 修复：必须找到最近两根有效的结构线，而不是用原始K线低点
        if len(dataframe) >= 2:
            # 从后往前找，找到最近两根有效的结构低点（structure_low > 0）
            structure_lows = []
            for i in range(len(dataframe) - 1, -1, -1):
                sl = dataframe.iloc[i].get('structure_low', 0)
                if sl > 0 and not np.isnan(sl):
                    structure_lows.append(sl)
                    if len(structure_lows) == 2:
                        break
            
            # 只有找到至少2根有效结构线才进行判断
            if len(structure_lows) >= 2:
                curr_structure_low = structure_lows[0]  # 最新的结构低点
                prev_structure_low = structure_lows[1]  # 上一根结构低点
                
                low_drop_pct = (prev_structure_low - curr_structure_low) / prev_structure_low

                # 只有当结构低点跌破且跌幅>阈值时才认为结构转弱
                if curr_structure_low < prev_structure_low and low_drop_pct > self.STRUCT_WEAK_PCT:
                    profit_pct = (current_rate - self.entry_price) / self.entry_price * 100
                    low_diff = prev_structure_low - curr_structure_low
                    logger.info(f"[{pair}] 结构转弱:")
                    logger.info(f"  - 入场价格: {self.entry_price:.6f}")
                    logger.info(f"  - 出场价格: {current_rate:.6f}")
                    logger.info(f"  - 盈亏: {profit_pct:+.3f}%")
                    logger.info(
                        f"  - 当前结构低 {curr_structure_low:.6f} < 前结构低 {prev_structure_low:.6f} (差距: {low_diff:.2f}, 跌幅: {low_drop_pct:.2%})")
                    exit_reason = "structure_weak"

        # 条件2：跌破下轨（失势）
        if exit_reason is None and bool(latest.get('is_below_lower', False)):
            profit_pct = (current_rate - self.entry_price) / self.entry_price * 100
            lower_val = latest.get('bb_lower_4h', np.nan)
            close_val = latest.get('close', np.nan)
            logger.info(f"[{pair}] 跌破下轨（失势）:")
            logger.info(f"  - 入场价格: {self.entry_price:.6f}")
            logger.info(f"  - 出场价格: {current_rate:.6f}")
            logger.info(f"  - 盈亏: {profit_pct:+.3f}%")
            logger.info(
                f"  - 收盘价 {close_val:.6f} <= 4h下轨 {lower_val if isinstance(lower_val, float) else float('nan'):.6f}")
            exit_reason = "4h_below_lower"

        # 如果触发任何出场条件，返回出场原因
        if exit_reason is not None:
            return exit_reason

        return None

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: str | None, side: str, **kwargs) -> bool:
        """确认交易入场（已删除所有安全检查）"""
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        if dataframe is None or len(dataframe) == 0:
            return False

        latest = dataframe.iloc[-1]

        # 最终检查：确保仍在持久 Armed 且当前有 HLH 信号
        armed_ok = bool(latest.get('armed_active', latest.get('is_armed', False)))
        hlh_ok = bool(latest.get('hlh_signal', False))
        if not (armed_ok and hlh_ok):
            logger.info(f"[{pair}] 入场确认失败: Armed={armed_ok}, HLH={hlh_ok}")
            return False

        logger.info(f"[{pair}] 入场确认成功:")
        logger.info(f"  - 4h布林宽度: {latest.get('bb_width_4h', np.nan):.3%}")
        logger.info(f"  - 1h收盘价: {latest.get('close', np.nan):.6f}")
        logger.info(
            f"  - 4h上轨: {latest.get('bb_upper_4h', np.nan):.6f}, 下轨: {latest.get('bb_lower_4h', np.nan):.6f}")
        logger.info(f"  - 1h HLH信号: {hlh_ok}")
        logger.info(f"  - 入场价格: {rate:.6f}")

        # 记录交易开仓信息
        self.trades_history.append({
            'pair': pair,
            'entry_time': current_time,
            'entry_price': rate,
            'exit_time': None,
            'exit_price': None,
            'exit_reason': None,
            'profit_pct': None,
            'bb_width': latest.get('bb_width', np.nan),
            'armed_active': latest.get('armed_active', False),
            'hlh_signal': latest.get('hlh_signal', False),
            'trade_id': len(self.trades_history)  # 简单的交易ID
        })

        return True

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str, amount: float,
                           rate: float, time_in_force: str, exit_reason: str,
                           current_time: datetime, **kwargs) -> bool:
        """确认交易出场"""
        profit_ratio = trade.calc_profit_ratio(rate)
        logger.info(f"[{pair}] 出场确认: 原因={exit_reason}, 价格={rate:.6f}, 盈亏={profit_ratio:.3%}")

        # 更新交易记录（找到最近的未平仓交易）
        for trade_record in reversed(self.trades_history):
            if trade_record['pair'] == pair and trade_record['exit_time'] is None:
                trade_record['exit_time'] = current_time
                trade_record['exit_price'] = rate
                trade_record['exit_reason'] = exit_reason
                trade_record['profit_pct'] = profit_ratio * 100
                trade_record['hold_hours'] = (current_time - trade_record['entry_time']).total_seconds() / 3600
                break

        return True

    def _dump_debug_trace(self, dataframe: DataFrame, metadata: dict) -> None:
        """将最近N行关键列导出到CSV，便于排查信号未触发原因"""
        if dataframe is None or dataframe.empty:
            return
        rows = int(getattr(self, 'debug_dump_rows', 300))
        # 导出1h数据、均线数据和4h布林带数据
        cols = [
            'date', 'open', 'high', 'low', 'close', 'volume',
            'ma20', 'is_above_ma20',
            'bb_upper_4h', 'bb_middle_4h', 'bb_lower_4h', 'bb_width_4h',
            'is_width_ok', 'is_breakout', 'is_below_lower', 'is_armed', 'armed_active',
            'structure_high', 'structure_low', 'is_new_structure', 'hlh_signal',
            'debug_entry_eval', 'enter_long', '4h_period_start'
        ]
        existing = [c for c in cols if c in dataframe.columns]
        if not existing:
            return
        out = dataframe.iloc[-rows:][existing].copy()

        # 将结构高低点的0值替换为空字符串（显示为空白而不是0）
        if 'structure_high' in out.columns:
            out['structure_high'] = out['structure_high'].replace(0.0, '')
        if 'structure_low' in out.columns:
            out['structure_low'] = out['structure_low'].replace(0.0, '')

        # 只在产生新结构线的行显示结构高低点，其他行显示为空白
        if 'is_new_structure' in dataframe.columns:
            # 获取is_new_structure列（需要从原始dataframe获取，因为可能不在cols中）
            is_new_structure_values = dataframe.iloc[-rows:]['is_new_structure'].fillna(False).astype(bool)
            # 将非新结构线的行的结构高低点设置为空字符串
            mask = ~is_new_structure_values
            if 'structure_high' in out.columns:
                out.loc[mask, 'structure_high'] = ''
            if 'structure_low' in out.columns:
                out.loc[mask, 'structure_low'] = ''

        out = self._apply_cn_headers(out)
        debug_dir = Path('user_data') / 'debug'
        debug_dir.mkdir(parents=True, exist_ok=True)
        safe_pair = str(metadata.get('pair', 'PAIR')).replace('/', '_')
        fname = debug_dir / f"BollingerHLH_{safe_pair}_{self.timeframe}.csv"
        # 覆盖写入最近窗口，便于随时查看当前状态
        # Windows 上若文件被 Excel 打开，会产生写入锁。尝试主文件写入，失败则写入带时间戳的备用文件。
        try:
            out.to_csv(fname, index=False, encoding='utf-8-sig')
            logger.info("[CSV] Wrote recent-window CSV: %s (rows=%d, cols=%d)", fname, len(out), len(out.columns))
        except PermissionError as e:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            alt = debug_dir / f"BollingerHLH_{safe_pair}_{self.timeframe}_{ts}.csv"
            out.to_csv(alt, index=False, encoding='utf-8-sig')
            logger.warning("[CSV] Primary file locked, wrote fallback: %s (reason: %s)", alt, str(e))

    def _log_hourly_dataframe(self, dataframe: DataFrame, metadata: dict) -> None:
        """打印回测阶段每小时的关键列（限制最近N行，避免日志过大）- 已禁用详细日志"""
        # 日志已禁用，只保留CSV导出功能
        pass

    def _dump_full_dataframe_trace(self, dataframe: DataFrame, metadata: dict) -> None:
        """导出全量1h DataFrame关键列到CSV（回测一次性导出）"""
        if dataframe is None or dataframe.empty:
            return
        cols = getattr(self, 'full_trace_columns', [])
        cols = [c for c in cols if c in dataframe.columns]
        if not cols:
            return
        out = dataframe[cols].copy()

        # 将结构高低点的0值替换为空字符串（显示为空白而不是0）
        if 'structure_high' in out.columns:
            out['structure_high'] = out['structure_high'].replace(0.0, '')
        if 'structure_low' in out.columns:
            out['structure_low'] = out['structure_low'].replace(0.0, '')

        # 只在产生新结构线的行显示结构高低点，其他行显示为空白
        if 'is_new_structure' in out.columns:
            # 将非新结构线的行的结构高低点设置为空字符串
            mask = ~out['is_new_structure'].fillna(False).astype(bool)
            if 'structure_high' in out.columns:
                out.loc[mask, 'structure_high'] = ''
            if 'structure_low' in out.columns:
                out.loc[mask, 'structure_low'] = ''

        out = self._apply_cn_headers(out)
        debug_dir = Path('user_data') / 'debug'
        debug_dir.mkdir(parents=True, exist_ok=True)
        safe_pair = str(metadata.get('pair', 'PAIR')).replace('/', '_')
        fname = debug_dir / f"BollingerHLH_{safe_pair}_{self.timeframe}_full.csv"
        # 同样处理 Windows 文件锁问题
        try:
            out.to_csv(fname, index=False, encoding='utf-8-sig')
            logger.info("[CSV] Wrote full CSV: %s (rows=%d, cols=%d)", fname, len(out), len(out.columns))
        except PermissionError as e:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            alt = debug_dir / f"BollingerHLH_{safe_pair}_{self.timeframe}_full_{ts}.csv"
            out.to_csv(alt, index=False, encoding='utf-8-sig')
            logger.warning("[CSV] Primary file locked, wrote fallback: %s (reason: %s)", alt, str(e))

        # 导出交易记录
        self._dump_trades_history(metadata)

    def _log_pretty_summary(self, df: DataFrame, pair: str | None) -> None:
        """打印与需求截图风格类似的汇总统计。"""
        if df is None or df.empty:
            return
        pair = pair or "PAIR"

        total = len(df)
        # Armed统计
        armed_mask = df.get('armed_active', False)
        if hasattr(armed_mask, 'fillna'):
            armed_mask = armed_mask.fillna(False)
        armed_cnt = int(armed_mask.sum())
        armed_hours = armed_cnt  # timeframe=1h
        armed_ratio = (armed_cnt / total * 100.0) if total > 0 else 0.0
        armed_entry_signals = int(((df.get('enter_long', 0) > 0) & armed_mask).sum())

        # 布林宽度统计（使用实时1h）
        bbw = df.get('bb_width')
        if bbw is not None:
            bbw = bbw.dropna() * 100.0
        if bbw is None or bbw.empty:
            bbw_avg = bbw_min = bbw_max = bbw_med = 0.0
        else:
            bbw_avg = float(bbw.mean())
            bbw_min = float(bbw.min())
            bbw_max = float(bbw.max())
            bbw_med = float(bbw.median())

        # 入场阈值（在评估点的宽度）
        entry_mask = df.get('debug_entry_eval', False)
        if hasattr(entry_mask, 'fillna'):
            entry_mask = entry_mask.fillna(False)
        entry_bbw = df.get('bb_width')
        if entry_bbw is not None:
            entry_bbw = entry_bbw[entry_mask].dropna() * 100.0
        if entry_bbw is None or entry_bbw.empty:
            e_avg = e_min = e_max = e_med = 0.0
        else:
            e_avg = float(entry_bbw.mean())
            e_min = float(entry_bbw.min())
            e_max = float(entry_bbw.max())
            e_med = float(entry_bbw.median())

        # HLH统计
        hlh_mask = df.get('hlh_signal', False)
        if hasattr(hlh_mask, 'fillna'):
            hlh_mask = hlh_mask.fillna(False)
        hlh_total = int(hlh_mask.sum())
        hlh_armed = int((hlh_mask & armed_mask).sum())
        enter_cnt = int((df.get('enter_long', 0) > 0).sum())
        hlh_conv = (enter_cnt / hlh_total * 100.0) if hlh_total > 0 else 0.0

        # 入场确认统计
        pending_confirms = int((df.get('entry_confirm_result',
                                       '') == '待确认').sum()) if 'entry_confirm_result' in df.columns else enter_cnt

        # 入场价格变化统计（在评估点）
        base_mask = entry_mask
        if int(base_mask.sum()) == 0:
            base_mask = (df.get('enter_long', 0) > 0)
        pct = (df['close'].pct_change() * 100.0).where(base_mask)
        pct = pct.dropna()
        if pct.empty:
            p_avg = 0.0
            up_n = down_n = 0
            up_ratio = down_ratio = 0.0
        else:
            p_avg = float(pct.mean())
            up_n = int((pct > 0).sum())
            down_n = int((pct < 0).sum())
            base_n = up_n + down_n
            up_ratio = (up_n / base_n * 100.0) if base_n > 0 else 0.0
            down_ratio = (down_n / base_n * 100.0) if base_n > 0 else 0.0

        # 输出
        logger.info("⭕ Armed状态统计：")
        logger.info("- Armed持续时间: %s 小时", f"{armed_hours}")
        logger.info("- Armed占比: %.2f%%", armed_ratio)
        logger.info("- Armed期间入场信号: %d 个", armed_entry_signals)

        logger.info("🖊 布林带宽度统计：")
        logger.info("- 平均宽度: %.2f%%", bbw_avg)
        logger.info("- 最小宽度: %.2f%%", bbw_min)
        logger.info("- 最大宽度: %.2f%%", bbw_max)
        logger.info("- 中位数宽度: %.2f%%", bbw_med)

        logger.info("🟦 入场阈值统计：")
        logger.info("- 平均: %.2f%%", e_avg)
        logger.info("- 最小: %.2f%%", e_min)
        logger.info("- 最大: %.2f%%", e_max)
        logger.info("- 中位数: %.2f%%", e_med)

        logger.info("🔵 HLH信号统计：")
        logger.info("- HLH信号总数: %d 次", hlh_total)
        logger.info("- 有Armed的HLH: %d 次（最终入场）", hlh_armed)
        logger.info("- HLH转化入场率: %.2f%%", hlh_conv)

        logger.info("✅ 入场确认统计：")
        logger.info("- 待确认: %d 次", pending_confirms)

        logger.info("✅ 入场价格变化统计：")
        logger.info("- 平均变化: %.2f%%", p_avg)
        logger.info("- 上涨: %d 次 (%.1f%%)", up_n, up_ratio)
        logger.info("- 下跌: %d 次 (%.1f%%)", down_n, down_ratio)

    def _dump_trades_history(self, metadata: dict) -> None:
        """导出交易历史记录到CSV"""
        if not self.trades_history:
            logger.info("[TRADES] 没有交易记录需要导出")
            return

        # 转换为DataFrame
        trades_df = pd.DataFrame(self.trades_history)

        # 重命名列为中文
        trades_df = trades_df.rename(columns={
            'pair': '交易对',
            'entry_time': '开仓时间',
            'entry_price': '开仓价格',
            'exit_time': '平仓时间',
            'exit_price': '平仓价格',
            'exit_reason': '平仓原因',
            'profit_pct': '盈亏百分比',
            'hold_hours': '持仓小时',
            'bb_width': '布林宽度',
            'armed_active': 'Armed状态',
            'hlh_signal': 'HLH信号',
            'trade_id': '交易ID'
        })

        # 保存到文件
        debug_dir = Path('user_data') / 'debug'
        debug_dir.mkdir(parents=True, exist_ok=True)
        safe_pair = str(metadata.get('pair', 'ALL')).replace('/', '_')
        fname = debug_dir / f"trades_history_{safe_pair}.csv"

        trades_df.to_csv(fname, index=False, encoding='utf-8-sig')
        logger.info("[TRADES] Exported %d trades to: %s", len(trades_df), fname)

        # 打印简单统计
        if len(trades_df) > 0:
            completed = trades_df[trades_df['平仓时间'].notna()]
            if len(completed) > 0:
                win_trades = len(completed[completed['盈亏百分比'] > 0])
                win_rate = win_trades / len(completed) * 100
                avg_profit = completed['盈亏百分比'].mean()
                logger.info("[TRADES] 统计: 总交易=%d, 已完成=%d, 胜率=%.2f%%, 平均盈亏=%.2f%%",
                            len(trades_df), len(completed), win_rate, avg_profit)

    def _apply_cn_headers(self, df: DataFrame) -> DataFrame:
        """将英文列名映射为中文表头（仅对存在的列生效）"""
        mapping = {
            # 1h数据
            'date': '时间',
            'open': '开盘价',
            'high': '最高价',
            'low': '最低价',
            'close': '收盘价',
            'volume': '成交量',
            # 均线数据
            'ma20': 'N小时均线',
            'is_above_ma20': '价格>均线',
            # 4h布林带数据
            'bb_upper_4h': '4h布林上轨',
            'bb_middle_4h': '4h布林中轨',
            'bb_lower_4h': '4h布林下轨',
            'bb_width_4h': '4h布林宽度',
            # 实时条件判断
            'is_width_ok': '宽度缩口(<=5.5%)',
            'is_breakout': '实时突破上轨',
            'is_below_lower': '跌破下轨',
            'is_armed': 'Armed触发',
            'armed_active': 'Armed持续',
            # 1h结构
            'structure_high': '结构高',
            'structure_low': '结构低',
            'is_new_structure': '新结构线',
            'hlh_signal': 'HLH信号',
            # 控制信号
            'debug_entry_eval': '入场评估',
            'enter_long': '入场信号',
            # 4h周期信息
            '4h_period_start': '4h周期起始小时',
        }
        # 仅重命名存在的列
        applicable = {k: v for k, v in mapping.items() if k in df.columns}
        return df.rename(columns=applicable)
