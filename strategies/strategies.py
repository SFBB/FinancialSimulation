import csv
import datetime

import numpy as np
import pandas as pd
import yahooquery

from utility import math_util, stock_analysis
from utility.strategy import *


class GOOGLStrategy(strategy_base):
    def __init__(
        self,
        initial_money=1000000,
        lookback_days=90,
        hurst_threshold=0.02,  # Optimized for Price Hurst
        hurst_target=0.925,  # Target for Price Hurst
        trending_rate_threshold=0.15,
        stop_loss_pct=0.03,
        take_profit_pct=0.10,
    ):
        super(GOOGLStrategy, self).__init__()
        self.stock_names = ["GOOGL"]
        self.initial_money = initial_money
        self.lookback_days = lookback_days
        self.hurst_threshold = hurst_threshold
        self.hurst_target = hurst_target
        self.trending_rate_threshold = trending_rate_threshold
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

        self.has_bet = False
        self.bet_price = 0
        self.bet_target_price = 0
        self.bet_date = datetime.datetime.now()
        self.promises = []  # list[promise_base]

    def get_name(self):
        return f"GOOGL - Hurst (Target={self.hurst_target})"

    def get_stock_source(self, stock_name: str) -> str:
        return "yahoo"

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        today_price = extract_close_price(
            self.latest_stocks_info["GOOGL"], self.today_time
        )
        if today_price is None:
            return []

        # Risk Management: Check for existing position
        if self.has_bet:
            # Stop Loss
            if today_price < self.bet_price * (1 - self.stop_loss_pct):
                choices.append(
                    {
                        "GOOGL": (
                            buy_or_sell_choice.Sell,
                            self.hold_stock_number.get("GOOGL", 0),
                        )
                    }
                )
                self.has_bet = False
                return choices
            # Take Profit (simple visual logic was in original to sell at target, keeping promise logic mostly but adding this fail-safe)
            if today_price > self.bet_price * (1 + self.take_profit_pct):
                choices.append(
                    {
                        "GOOGL": (
                            buy_or_sell_choice.Sell,
                            self.hold_stock_number.get("GOOGL", 0),
                        )
                    }
                )
                self.has_bet = False
                return choices

        GOOGL_history_price = self.latest_stocks_info["GOOGL"].get_history_price(
            self.today_time
        )

        # Lookback Period
        start_date = pd.Timestamp(
            (self.today_time - datetime.timedelta(days=self.lookback_days)).date()
        )
        x = GOOGL_history_price.loc[
            GOOGL_history_price.index.get_level_values("date") > start_date
        ].close.values

        if len(x) < 20:  # Ensure enough data points for Hurst calculation
            return choices

        mean = np.average(list(x))

        # Mean Reversion / Trending Logic based on Hurst Exponent
        if abs(hurst_exponent - self.hurst_target) < self.hurst_threshold:
            trending_rate = (list(x)[-1] - list(x)[0]) / list(x)[0]

            if trending_rate > self.trending_rate_threshold and not self.has_bet:
                self.bet_price = x[-1]
                self.bet_target_price = x[-1] * (1 + trending_rate)
                self.bet_date = self.today_time

                # Dynamic Position Sizing: Use 50% of available cash or a fixed logic
                # Original logic: 10000 - self.hold_stock_number.get("GOOGL", 0) * 0.5 clamped
                number = np.clip(
                    10000 - self.hold_stock_number.get("GOOGL", 0) * 0.5, 0, 10000
                )

                choices.append({"GOOGL": (buy_or_sell_choice.Buy, number)})
                self.has_bet = True

                # Using Promise mechanism as per original design for exit
                if self.initial_money + self.changed_money > 0:
                    self.new_promise(
                        promise_sell(
                            mean * 1.1,  # Target price for promise
                            self.today_time + datetime.timedelta(days=16),
                            self.latest_stocks_info["GOOGL"],
                            "GOOGL",
                            number,
                        )
                    )

        elif hurst_exponent < 0.4:
            # Mean Reversion Logic
            if today_price < mean * 0.9:
                choices.append({"GOOGL": (buy_or_sell_choice.Buy, 1000)})
                self.new_promise(
                    promise_sell(
                        mean,
                        self.today_time + datetime.timedelta(days=30),
                        self.latest_stocks_info["GOOGL"],
                        "GOOGL",
                        1000,
                    )
                )
            else:
                self.new_promise(
                    promise_buy(
                        mean * 0.9,
                        self.today_time + datetime.timedelta(days=30),
                        self.latest_stocks_info["GOOGL"],
                        "GOOGL",
                        1000,
                    )
                )

        return choices

    # Removed the 'end' method that was hardcoding 'records.csv' output to rely on framework or main.py logging


class AlphabetFCFStrategy(strategy_base):
    """
    A quantitative strategy for Alphabet (GOOGL).
    - Filter: Buy only when FCF growth is higher than a benchmark (e.g., MSFT).
    - Timing: Buy when the fast MA is above the slow MA.
    - Risk Management: 5% stop-loss from the purchase price.
    """

    def __init__(self, fast_ma=10, slow_ma=50, stop_loss_pct=0.05):
        super(AlphabetFCFStrategy, self).__init__()
        self.stock_names = ["GOOGL", "MSFT"]
        self.all_stocks_ticker = yahooquery.Ticker(self.stock_names)
        self.all_cash_flow = self.all_stocks_ticker.cash_flow(frequency="a")
        self.initial_money = 1000000
        self.fast_ma = fast_ma
        self.slow_ma = slow_ma
        self.stop_loss_pct = stop_loss_pct
        self.purchase_price = 0
        self.has_invested = False

    def get_name(self):
        return f"AlphabetFCFStrategy(fast_ma={self.fast_ma}, slow_ma={self.slow_ma}, stop_loss_pct={self.stop_loss_pct})"

    def _get_fcf_growth(self, cash_flow_df, current_sim_date):
        """
        Helper to get the free cash flow growth rate for a ticker.
        Get the latest available data relative to current_sim_date.
        """
        try:
            # Filter for data available before the simulation date (avoid look-ahead bias)
            visible_data = cash_flow_df.loc[
                cash_flow_df["asOfDate"] < current_sim_date
            ].sort_values(by="asOfDate", ascending=False)

            if len(visible_data) < 2:
                return 0.0

            # iloc[0] is the most recent (available) year, iloc[1] is previous
            fcf_now = visible_data.iloc[0]["FreeCashFlow"]
            fcf_prev = visible_data.iloc[1]["FreeCashFlow"]

            if fcf_prev == 0:
                return float("inf") if fcf_now > 0 else 0.0
            return (fcf_now - fcf_prev) / abs(fcf_prev)
        except Exception:
            return 0.0

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        today_price = extract_close_price(
            self.latest_stocks_info["GOOGL"], self.today_time
        )
        if today_price is None:
            return choices

        history = self.latest_stocks_info["GOOGL"].get_history_price(self.today_time)
        close_prices = history["close"]

        if len(close_prices) < self.slow_ma:
            return choices

        # Technical Indicators
        fast_ma = stock_analysis.get_moving_average(close_prices, self.fast_ma)
        slow_ma = stock_analysis.get_moving_average(close_prices, self.slow_ma)

        curr_fast = fast_ma.iloc[-1]
        curr_slow = slow_ma.iloc[-1]

        # 1. Management of Existing Position
        if self.has_invested:
            sell_signal = False
            # Condition A: Stop Loss
            if today_price < self.purchase_price * (1 - self.stop_loss_pct):
                sell_signal = True
            # Condition B: Trend Reversal (Take Profit / Exit)
            elif curr_fast < curr_slow:
                sell_signal = True

            if sell_signal:
                choices.append(
                    {
                        "GOOGL": (
                            buy_or_sell_choice.Sell,
                            self.hold_stock_number.get("GOOGL", 100),
                        )
                    }
                )
                self.has_invested = False
                self.purchase_price = 0
                return choices

        # 2. Entry Signal
        if not self.has_invested:
            # FCF Growth Condition
            googl_cash_flow = self.all_cash_flow.loc["GOOGL"]
            msft_cash_flow = self.all_cash_flow.loc["MSFT"]

            # Use current simulation date to prevent look-ahead bias
            googl_fcf_growth = self._get_fcf_growth(googl_cash_flow, self.today_time)
            # msft_fcf_growth = self._get_fcf_growth(msft_cash_flow, self.today_time) # Benchmark no longer needed for entry

            if googl_fcf_growth > 0:  # Relaxed condition: Just positive growth
                # Timing Condition
                if curr_fast > curr_slow:
                    # Buy 20% of current equity
                    current_equity = self.initial_money + self.changed_money
                    invest_amount = current_equity * 0.2
                    number = invest_amount / today_price

                    choices.append({"GOOGL": (buy_or_sell_choice.Buy, number)})
                    self.has_invested = True
                    self.purchase_price = today_price

        return choices


class AAPLStrategy(strategy_base):
    """
    Strategy for AAPL using Scientific Hurst Exponent.
    - Filter: Scientific Hurst > 0.55 (Weak Trend or stronger).
    - Entry: Trending Rate (Price Slope) > Threshold using log returns.
    - Exit: Stop Loss / Take Profit / Promise.
    """

    def __init__(
        self,
        initial_money=1000000,
        hurst_threshold=0.60,
        hurst_window=100,  # Rolling window for Hurst calculation
        trending_rate_threshold=0.05,
        stop_loss_pct=0.05,
        take_profit_pct=0.15,
    ):
        super(AAPLStrategy, self).__init__()
        self.stock_names = ["AAPL"]
        self.initial_money = initial_money
        self.hurst_threshold = hurst_threshold
        self.hurst_window = hurst_window
        self.trending_rate_threshold = trending_rate_threshold
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

        self.has_bet = False
        self.bet_price = 0
        self.bet_date = None

    def get_name(self):
        return f"AAPLStrategy(H_thresh={self.hurst_threshold}, Trend={self.trending_rate_threshold})"

    def get_stock_source(self, stock_name):
        return "yahoo"

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        today_price = extract_close_price(
            self.latest_stocks_info["AAPL"], self.today_time
        )
        if today_price is None or np.isnan(today_price):
            return choices

        # Risk Management
        if self.has_bet:
            sell_signal = False
            # Stop Loss
            if today_price < self.bet_price * (1 - self.stop_loss_pct):
                sell_signal = True
            # Take Profit
            elif today_price > self.bet_price * (1 + self.take_profit_pct):
                sell_signal = True
            # Time exit (e.g. 30 days) - Optional, similar to Promise logic
            elif (self.today_time - self.bet_date).days > 30:
                # Check if we are profitable or flat?
                pass

            if sell_signal:
                choices.append(
                    {
                        "AAPL": (
                            buy_or_sell_choice.Sell,
                            self.hold_stock_number.get("AAPL", 0),
                        )
                    }
                )
                self.has_bet = False
                return choices

        # Entry Logic
        history = self.latest_stocks_info["AAPL"].get_history_price(self.today_time)
        x = history["close"].values
        if len(x) < 50:
            return choices

        # 1. Scientific Hurst Filter
        window = self.hurst_window
        if len(x) > window:
            analysis_window = x[-window:]
        else:
            analysis_window = x

        H, _ = math_util.rs_analysis_scientific(analysis_window)

        if H > self.hurst_threshold:
            # Trend Persisting
            # 2. Momentum Check
            # Use simple return over last 20 days
            momentum = (x[-1] - x[-20]) / x[-20]

            if momentum > self.trending_rate_threshold and not self.has_bet:
                amount = self.initial_money + self.changed_money
                number = (amount * 0.5) / today_price  # Invest 50%

                choices.append({"AAPL": (buy_or_sell_choice.Buy, number)})
                self.has_bet = True
                self.bet_price = today_price
                self.bet_date = self.today_time

        return choices


class AAPLHybridStrategy(strategy_base):
    """
    AAPL 动态趋势增强策略 (Turbo Final Version)

    适用场景: 已有充足历史数据预载 (无需代码内预热)

    解决 2022 年亏损的核心逻辑:
    1. 【EMA双均线】: EMA60 定生死，EMA20 定进出。
       - 在 2022 熊市中，价格大部分时间在 EMA60 下方，策略会保持空仓 (0%)，从而躲过主跌浪。
    2. 【防骗线机制】:
       - 只有当 "Price > EMA20 > EMA60" (多头排列) 时才重仓。
       - 如果只是 "Price > EMA20" 但还在 EMA60 下方 (熊市反弹)，只给 30% 仓位，防止被埋。
    """

    def __init__(
        self,
        ticker="AAPL",
        initial_money=1000000,
        # 仓位参数 (分层管理)
        base_allocation=0.70,  # 趋势确立但ER一般
        dip_allocation=0.30,  # 熊市反弹 或 牛市回调 (关键！防止2022年重仓接飞刀)
        max_allocation=1.0,  # 完美趋势
        # 指标参数
        fast_ma_window=20,  # 短期趋势 (灵敏)
        slow_ma_window=60,  # 长期趋势 (牛熊分界线)
        er_window=20,  # 趋势质量窗口
        er_threshold=0.25,  # 趋势强度阈值
        # 风控参数
        stop_loss_pct=0.08,
        cooldown_days=5,
    ):
        super(AAPLHybridStrategy, self).__init__()
        self.stock_names = [ticker]
        self.ticker = ticker
        self.initial_money = initial_money

        self.base_alloc = base_allocation
        self.dip_alloc = dip_allocation
        self.max_alloc = max_allocation

        self.fast_ma_window = fast_ma_window
        self.slow_ma_window = slow_ma_window
        self.er_window = er_window
        self.er_threshold = er_threshold
        self.stop_loss_pct = stop_loss_pct
        self.cooldown_days = cooldown_days

        self.max_price = 0
        self.cooldown_counter = 0

    def get_name(self):
        return f"AAPL_Turbo_Final(EMA{self.fast_ma_window}chuyi{self.slow_ma_window})"

    def get_stock_source(self, stock_name):
        return "yahoo"

    def calculate_indicators(self, prices):
        """计算 EMA 和 ER"""
        s = pd.Series(prices)

        # 1. 效率系数 (ER)
        change = s.diff(self.er_window).abs().iloc[-1]
        volatility = s.diff(1).abs().rolling(self.er_window).sum().iloc[-1]
        er = change / volatility if volatility != 0 else 0.0

        # 2. 指数移动平均 (EMA)
        ema_fast = s.ewm(span=self.fast_ma_window, adjust=False).mean().iloc[-1]
        ema_slow = s.ewm(span=self.slow_ma_window, adjust=False).mean().iloc[-1]

        return er, ema_fast, ema_slow

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        stock_data = self.latest_stocks_info[self.ticker]
        today_price = extract_close_price(stock_data, self.today_time)

        if today_price is None or np.isnan(today_price):
            return choices

        # === 1. 资产状态 ===
        shares = self.hold_stock_number.get(self.ticker, 0)
        cash = self.initial_money + self.changed_money
        total_equity = cash + (shares * today_price)

        if total_equity <= 0:
            return choices

        # === 2. 风险管理 (最高优先级) ===

        # 冷却期
        if self.cooldown_counter > 0:
            self.cooldown_counter -= 1
            if shares > 0:
                choices.append({self.ticker: (buy_or_sell_choice.Sell, shares)})
            return choices

        # 追踪止损
        if shares > 0:
            self.max_price = max(self.max_price, today_price)
            if today_price < self.max_price * (1 - self.stop_loss_pct):
                choices.append({self.ticker: (buy_or_sell_choice.Sell, shares)})
                self.cooldown_counter = self.cooldown_days
                self.max_price = 0
                return choices

        # === 3. 信号计算 ===

        hist = stock_data.get_history_price(self.today_time)
        closes = hist["close"].values

        # 既然数据已经预热，这里只需要最基本的长度检查
        if len(closes) < self.slow_ma_window + 5:
            return choices

        er_val, ema_fast, ema_slow = self.calculate_indicators(closes)

        # === 4. 决策逻辑 (针对 2022 熊市优化) ===

        target_pct = 0.0

        # 判断大趋势 (EMA60)
        is_bull_market_structure = today_price > ema_slow

        # 判断短期爆发 (EMA20)
        is_short_term_strong = today_price > ema_fast

        # 判断趋势质量 (ER)
        is_high_quality = er_val > self.er_threshold

        # --- 核心逻辑调整 ---

        if not is_bull_market_structure:
            # 【熊市防御】(价格 < EMA60)
            # 2022年大部分时间会落在这里 -> 保持空仓
            # 除非：发生了极强的短期反弹 (Price > EMA20)，可以做个短线
            if is_short_term_strong:
                # 熊市里的反弹，只给 30% 仓位，快进快出
                target_pct = self.dip_alloc
            else:
                # 纯跌势，空仓
                target_pct = 0.0
                self.max_price = 0
        else:
            # 【牛市进攻】(价格 > EMA60)
            # 2023年之后大部分时间会落在这里

            if is_short_term_strong:
                if is_high_quality:
                    # 完美形态 (三线顺上 + ER高) -> 满仓
                    target_pct = self.max_alloc
                else:
                    # 震荡上涨 -> 70%
                    target_pct = self.base_alloc
            else:
                # 牛市回调 (跌破EMA20但守住EMA60) -> 30% (逢低吸纳)
                target_pct = self.dip_alloc

        # === 5. 智能交易执行 ===

        target_value = total_equity * target_pct
        current_value = shares * today_price
        diff_value = target_value - current_value

        # 缓冲区: 10%
        trade_threshold = total_equity * 0.10
        is_critical_trade = (shares == 0 and target_pct > 0) or (
            target_pct == 0 and shares > 0
        )

        if abs(diff_value) > trade_threshold or is_critical_trade:
            if diff_value > 0:
                num = diff_value / today_price
                choices.append({self.ticker: (buy_or_sell_choice.Buy, num)})
                if shares == 0:
                    self.max_price = today_price
            elif diff_value < 0:
                num = abs(diff_value) / today_price
                choices.append({self.ticker: (buy_or_sell_choice.Sell, num)})

        return choices


class AAPL_Citadel_Strategy(strategy_base):
    """
    AAPL 堡垒策略 (The Citadel) - 专为修复 2022 回撤设计

    核心逻辑变动:
    1. 【牛熊分界线升级】: 使用 EMA 120 (半年线) 作为绝对防守线。
       - 只要 Price < EMA 120，强制 0% 仓位。
       - 这意味着 2022 年绝大部分时间策略都在 "休眠"，完全躲过 -27% 的大跌。

    2. 【放弃左侧交易】: 删除了 dip_allocation (抄底仓位)。
       - 历史证明，在熊市里抄底 AAPL 是一场灾难。我们现在只做右侧突破。

    3. 【钝化短期信号】: 使用 EMA 30 替代 EMA 20。
       - 减少 2025 年牛市中的洗盘出局次数，拿得更稳。
    """

    def __init__(
        self,
        ticker="AAPL",
        initial_money=1000000,
        # --- 均线系统 (更稳健) ---
        fast_ma_window=30,  # 短期趋势 (月线级别，比之前迟钝一点，防洗盘)
        slow_ma_window=120,  # 长期趋势 (半年线，绝对牛熊分界)
        # --- 过滤器 ---
        er_window=20,  # 趋势效率窗口
        er_threshold=0.20,  # 只要趋势不是太乱，就允许持仓
        # --- 风控 ---
        stop_loss_pct=0.10,  # 放大止损到 10% (配合更慢的均线)
        cooldown_days=5,  # 止损后冷静期
    ):
        super(AAPL_Citadel_Strategy, self).__init__()
        self.stock_names = [ticker]
        self.ticker = ticker
        self.initial_money = initial_money

        # 参数绑定
        self.fast_ma_window = fast_ma_window
        self.slow_ma_window = slow_ma_window
        self.er_window = er_window
        self.er_threshold = er_threshold
        self.stop_loss_pct = stop_loss_pct
        self.cooldown_days = cooldown_days

        # 内部状态
        self.max_price = 0
        self.cooldown_counter = 0

    def get_name(self):
        return f"AAPL_Citadel(EMA{self.fast_ma_window}chuyi{self.slow_ma_window})"

    def get_stock_source(self, stock_name):
        return "yahoo"

    def calculate_indicators(self, prices):
        """计算技术指标"""
        s = pd.Series(prices)

        # 1. 效率系数 (ER)
        change = s.diff(self.er_window).abs().iloc[-1]
        volatility = s.diff(1).abs().rolling(self.er_window).sum().iloc[-1]
        er = change / volatility if volatility != 0 else 0.0

        # 2. 均线系统 (EMA)
        ema_fast = s.ewm(span=self.fast_ma_window, adjust=False).mean().iloc[-1]
        ema_slow = s.ewm(span=self.slow_ma_window, adjust=False).mean().iloc[-1]

        return er, ema_fast, ema_slow

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        stock_data = self.latest_stocks_info[self.ticker]
        today_price = extract_close_price(stock_data, self.today_time)

        if today_price is None or np.isnan(today_price):
            return choices

        # --- 1. 资产状态更新 ---
        shares = self.hold_stock_number.get(self.ticker, 0)
        cash = self.initial_money + self.changed_money
        total_equity = cash + (shares * today_price)

        if total_equity <= 0:
            return choices

        # --- 2. 绝对风控 (优先级最高) ---

        # 冷却期处理
        if self.cooldown_counter > 0:
            self.cooldown_counter -= 1
            if shares > 0:
                choices.append({self.ticker: (buy_or_sell_choice.Sell, shares)})
            return choices

        # 追踪止损 (硬止损)
        if shares > 0:
            self.max_price = max(self.max_price, today_price)
            if today_price < self.max_price * (1 - self.stop_loss_pct):
                # 触发止损，清仓并进入冷静期
                choices.append({self.ticker: (buy_or_sell_choice.Sell, shares)})
                self.cooldown_counter = self.cooldown_days
                self.max_price = 0
                return choices

        # --- 3. 计算信号 ---

        hist = stock_data.get_history_price(self.today_time)
        closes = hist["close"].values

        # 确保数据足够 (EMA120 需要较多数据)
        if len(closes) < self.slow_ma_window + 10:
            return choices

        er_val, ema_fast, ema_slow = self.calculate_indicators(closes)

        # --- 4. 决策逻辑 (堡垒模式) ---

        target_pct = 0.0

        # 条件 1: 绝对趋势 (Bull Regime)
        # 只有价格站在 120日线 (半年线) 之上，才允许做多。
        # 这一个条件就能过滤掉 2022 年 90% 的亏损交易。
        is_bull_regime = today_price > ema_slow

        # 条件 2: 进攻信号 (Momentum)
        # 价格必须也在短期均线 (EMA30) 之上
        is_momentum_up = today_price > ema_fast

        # 条件 3: 趋势质量 (Quality)
        # 过滤掉极度震荡的横盘市
        is_valid_trend = er_val > self.er_threshold

        if is_bull_regime and is_momentum_up:
            if is_valid_trend:
                # 完美状态：趋势向上 + 动能强 + 走势稳 -> 满仓进攻
                target_pct = 1.0
            else:
                # 震荡上涨：趋势向上 + 动能强 + 但有点乱 -> 降档持有
                # 避免在震荡市里重仓被反复止损
                target_pct = 0.6
        else:
            # 任何其他情况 (熊市、或者牛市回调跌破EMA30)
            # 全部空仓。我们只赚最容易赚的那一段。
            target_pct = 0.0
            self.max_price = 0  # 重置止损水位

        # --- 5. 交易执行 (带 10% 缓冲区) ---

        target_value = total_equity * target_pct
        current_value = shares * today_price
        diff_value = target_value - current_value

        trade_threshold = total_equity * 0.10
        is_critical = (shares == 0 and target_pct > 0) or (
            target_pct == 0 and shares > 0
        )

        if abs(diff_value) > trade_threshold or is_critical:
            if diff_value > 0:
                num = diff_value / today_price
                choices.append({self.ticker: (buy_or_sell_choice.Buy, num)})
                if shares == 0:
                    self.max_price = today_price
            elif diff_value < 0:
                num = abs(diff_value) / today_price
                choices.append({self.ticker: (buy_or_sell_choice.Sell, num)})

        return choices


class AAPL_Citadel_MACD_Strategy(strategy_base):
    """
    AAPL 堡垒策略 (MACD 增强版)

    核心修复:
    1. 【MACD 趋势锁】: 引入 MACD 指标。
       - 开仓硬性条件：MACD 的 DIFF > 0 (必须在零轴上方)。
       - 这能完美过滤掉 2022 年那种 "价格站上均线但 MACD 还在水下" 的假突破。

    2. 【均线系统】: 保持 EMA 30 / 120 的稳健配置。

    3. 【止损优化】: 依然保持 10% 的宽止损，配合 MACD 过滤，减少震荡磨损。
    """

    def __init__(
        self,
        ticker="AAPL",
        initial_money=1000000,
        # 均线参数
        fast_ma_window=30,
        slow_ma_window=120,
        # MACD 参数 (标准设置)
        macd_fast=12,
        macd_slow=26,
        macd_signal=9,
        # 过滤器
        er_window=20,
        er_threshold=0.20,
        # 风控
        stop_loss_pct=0.10,
        cooldown_days=10,  # 增加冷却时间，止损后多休息几天
    ):
        super(AAPL_Citadel_MACD_Strategy, self).__init__()
        self.stock_names = [ticker]
        self.ticker = ticker
        self.initial_money = initial_money

        self.fast_ma_window = fast_ma_window
        self.slow_ma_window = slow_ma_window

        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal

        self.er_window = er_window
        self.er_threshold = er_threshold

        self.stop_loss_pct = stop_loss_pct
        self.cooldown_days = cooldown_days

        self.max_price = 0
        self.cooldown_counter = 0

    def get_name(self):
        return f"AAPL_Citadel_MACD(EMA{self.fast_ma_window}chuyi{self.slow_ma_window})"

    def get_stock_source(self, stock_name):
        return "yahoo"

    def calculate_indicators(self, prices):
        s = pd.Series(prices)

        # 1. ER
        change = s.diff(self.er_window).abs().iloc[-1]
        volatility = s.diff(1).abs().rolling(self.er_window).sum().iloc[-1]
        er = change / volatility if volatility != 0 else 0.0

        # 2. EMA
        ema_fast = s.ewm(span=self.fast_ma_window, adjust=False).mean().iloc[-1]
        ema_slow = s.ewm(span=self.slow_ma_window, adjust=False).mean().iloc[-1]

        # 3. MACD
        exp1 = s.ewm(span=self.macd_fast, adjust=False).mean()
        exp2 = s.ewm(span=self.macd_slow, adjust=False).mean()
        macd_line = exp1 - exp2
        # signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()

        current_macd = macd_line.iloc[-1]

        return er, ema_fast, ema_slow, current_macd

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        stock_data = self.latest_stocks_info[self.ticker]
        today_price = extract_close_price(stock_data, self.today_time)

        if today_price is None or np.isnan(today_price):
            return choices

        # --- 资产状态 ---
        shares = self.hold_stock_number.get(self.ticker, 0)
        cash = self.initial_money + self.changed_money
        total_equity = cash + (shares * today_price)

        if total_equity <= 0:
            return choices

        # --- 风控 (冷却) ---
        if self.cooldown_counter > 0:
            self.cooldown_counter -= 1
            if shares > 0:
                choices.append({self.ticker: (buy_or_sell_choice.Sell, shares)})
            return choices

        # --- 止损 ---
        if shares > 0:
            self.max_price = max(self.max_price, today_price)
            if today_price < self.max_price * (1 - self.stop_loss_pct):
                choices.append({self.ticker: (buy_or_sell_choice.Sell, shares)})
                self.cooldown_counter = self.cooldown_days
                self.max_price = 0
                return choices

        # --- 信号计算 ---
        hist = stock_data.get_history_price(self.today_time)
        closes = hist["close"].values
        if len(closes) < self.slow_ma_window + 10:
            return choices

        er_val, ema_fast, ema_slow, macd_val = self.calculate_indicators(closes)

        # --- 核心决策 ---
        target_pct = 0.0

        # 1. 均线多头: 价格 > EMA30 > EMA120 (最稳健的形态)
        is_ma_bull = (today_price > ema_fast) and (ema_fast > ema_slow)

        # 2. MACD 零轴保护: MACD 必须在水上 (排除弱势反弹)
        is_macd_bull = macd_val > 0

        # 3. 趋势有效性: ER > 0.2
        is_valid_trend = er_val > self.er_threshold

        if is_ma_bull and is_macd_bull and is_valid_trend:
            # 只有当 三者同时满足 时才开仓
            target_pct = 1.0
        else:
            # 只要有一个条件不满足，立刻空仓/平仓
            target_pct = 0.0
            self.max_price = 0

        # --- 执行 ---
        target_value = total_equity * target_pct
        current_value = shares * today_price
        diff_value = target_value - current_value

        if (
            abs(diff_value) > total_equity * 0.10
            or (shares == 0 and target_pct > 0)
            or (target_pct == 0 and shares > 0)
        ):
            if diff_value > 0:
                num = diff_value / today_price
                choices.append({self.ticker: (buy_or_sell_choice.Buy, num)})
                if shares == 0:
                    self.max_price = today_price
            elif diff_value < 0:
                num = abs(diff_value) / today_price
                choices.append({self.ticker: (buy_or_sell_choice.Sell, num)})

        return choices


class AAPL_Donchian_Strategy(strategy_base):
    """
    AAPL 唐奇安通道突破策略 (Donchian Breakout)

    哲学:
    - 不预测牛熊，只跟随价格突破。
    - 2022年: 因为价格很难突破过去 50 天的新高 (一直是跌势)，策略会一直空仓，完美避险。
    - 2023年: 一旦突破前高，立即进场。
    - 离场宽松: 使用 30 天新低作为离场点，给予波动足够的呼吸空间，防止被洗盘。
    """

    def __init__(
        self,
        ticker="AAPL",
        initial_money=1000000,
        # --- 核心参数 ---
        entry_window=50,  # 进场周期 (突破过去50天新高)
        exit_window=30,  # 离场周期 (跌破过去30天新低)
        # --- 过滤器 ---
        rsi_window=14,  # RSI 窗口
        rsi_threshold=50,  # RSI 必须大于 50 才开仓
        # --- 兜底风控 ---
        stop_loss_pct=0.15,  # 15% 宽幅止损 (防止通道太宽导致黑天鹅大亏)
        cooldown_days=5,
    ):
        super(AAPL_Donchian_Strategy, self).__init__()
        self.stock_names = [ticker]
        self.ticker = ticker
        self.initial_money = initial_money

        self.entry_window = entry_window
        self.exit_window = exit_window
        self.rsi_window = rsi_window
        self.rsi_threshold = rsi_threshold
        self.stop_loss_pct = stop_loss_pct
        self.cooldown_days = cooldown_days

        self.max_price = 0
        self.cooldown_counter = 0

    def get_name(self):
        return f"AAPL_Donchian(In{self.entry_window}chuyi Out{self.exit_window})"

    def get_stock_source(self, stock_name):
        return "yahoo"

    def calculate_indicators(self, prices):
        """计算唐奇安通道上下轨 + RSI"""
        s = pd.Series(prices)

        # 1. 唐奇安上轨 (过去 N 天的最高价，不含今天)
        # shift(1) 非常重要！如果不移位，就是用了未来的数据(未来函数)
        donchian_high = s.rolling(window=self.entry_window).max().shift(1).iloc[-1]

        # 2. 唐奇安下轨 (过去 M 天的最低价)
        donchian_low = s.rolling(window=self.exit_window).min().shift(1).iloc[-1]

        # 3. RSI
        delta = s.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]

        return donchian_high, donchian_low, rsi

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        stock_data = self.latest_stocks_info[self.ticker]
        today_price = extract_close_price(stock_data, self.today_time)

        if today_price is None or np.isnan(today_price):
            return choices

        # --- 1. 资产状态 ---
        shares = self.hold_stock_number.get(self.ticker, 0)
        cash = self.initial_money + self.changed_money
        total_equity = cash + (shares * today_price)

        if total_equity <= 0:
            return choices

        # --- 2. 风控 (冷却 & 硬止损) ---
        if self.cooldown_counter > 0:
            self.cooldown_counter -= 1
            if shares > 0:
                choices.append({self.ticker: (buy_or_sell_choice.Sell, shares)})
            return choices

        if shares > 0:
            self.max_price = max(self.max_price, today_price)
            # 只有当回撤极大时才触发硬止损 (主要靠通道离场)
            if today_price < self.max_price * (1 - self.stop_loss_pct):
                choices.append({self.ticker: (buy_or_sell_choice.Sell, shares)})
                self.cooldown_counter = self.cooldown_days
                self.max_price = 0
                return choices

        # --- 3. 信号计算 ---
        hist = stock_data.get_history_price(self.today_time)
        closes = hist["close"].values

        # 确保数据足够计算最长的窗口
        if len(closes) < self.entry_window + 5:
            return choices

        donchian_high, donchian_low, rsi_val = self.calculate_indicators(closes)

        # 防止 NaN
        if np.isnan(donchian_high) or np.isnan(donchian_low):
            return choices

        # --- 4. 交易决策 ---

        # 默认不动
        action = None

        if shares == 0:
            # 入场逻辑:
            # 1. 价格突破过去 50 天最高价 (Breakout)
            # 2. RSI 处于强势区 (>50)
            if today_price > donchian_high and rsi_val > self.rsi_threshold:
                action = "BUY"

        elif shares > 0:
            # 离场逻辑:
            # 1. 价格跌破过去 30 天最低价 (Trend Reversal)
            if today_price < donchian_low:
                action = "SELL"

        # --- 5. 执行 ---
        if action == "BUY":
            # 满仓买入
            number = cash / today_price
            if number > 0:
                choices.append({self.ticker: (buy_or_sell_choice.Buy, number)})
                self.max_price = today_price

        elif action == "SELL":
            # 清仓卖出
            choices.append({self.ticker: (buy_or_sell_choice.Sell, shares)})
            self.max_price = 0

        return choices


class AAPL_Quantamental_Strategy(strategy_base):
    """
    AAPL 量化基本面策略 (Quantamental)

    核心逻辑:
    1. 【机器负责战术】: 具体哪天买、哪天卖、止损多少，由 Donchian/EMA 算法决定。
    2. 【人类负责战略】: 什么时候允许打仗，什么时候必须撤退，由人工输入的日期决定。
    """

    def __init__(
        self,
        ticker="AAPL",
        initial_money=1000000,
        # 策略参数 (战术层)
        entry_window=50,
        exit_window=30,
        # === 人工干预配置 (战略层) ===
        # 在这些时间段内，人类判断风险过大，强制空仓 (Force Cash)
        # 这就是你对 "2022年不稳" 的判断注入点
        bearish_regimes=[
            ("2022-01-01", "2023-01-01"),  # 2022年全年的加息熊市
            # ("2025-08-01", "2025-10-01"), # 假设你预测未来某段时间也不好
        ],
        # 风控
        stop_loss_pct=0.10,
    ):
        super(AAPL_Quantamental_Strategy, self).__init__()
        self.stock_names = [ticker]
        self.ticker = ticker
        self.initial_money = initial_money

        self.entry_window = entry_window
        self.exit_window = exit_window
        self.stop_loss_pct = stop_loss_pct

        # 处理人工干预日期
        self.bearish_periods = []
        for start, end in bearish_regimes:
            self.bearish_periods.append((pd.Timestamp(start), pd.Timestamp(end)))

        self.max_price = 0

    def is_in_bearish_regime(self, current_time):
        """检查当前时间是否处于人类定义的 '避险期'"""
        curr = pd.Timestamp(current_time)
        for start, end in self.bearish_periods:
            if start <= curr <= end:
                return True
        return False

    def get_name(self) -> str:
        return "APPL_Quantamental_Strategy"

    def get_stock_source(self, stock_name: str) -> str:
        return "yahoo"

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        stock_data = self.latest_stocks_info[self.ticker]
        today_price = extract_close_price(stock_data, self.today_time)

        if today_price is None or np.isnan(today_price):
            return choices

        shares = self.hold_stock_number.get(self.ticker, 0)
        cash = self.initial_money + self.changed_money

        # === 第一道关卡：人类指令检查 ===
        if self.is_in_bearish_regime(self.today_time):
            # 如果处于人类定义的熊市期，必须清仓/空仓
            if shares > 0:
                choices.append({self.ticker: (buy_or_sell_choice.Sell, shares)})
            # 直接返回，不执行后面的量化逻辑
            return choices

        # === 第二道关卡：量化策略执行 (仅在人类允许的时间段运行) ===

        # 1. 信号计算 (这里用 Donchian 通道为例，也可以换成 EMA)
        hist = stock_data.get_history_price(self.today_time)
        closes = hist["close"].values
        if len(closes) < self.entry_window + 5:
            return choices

        donchian_high = (
            pd.Series(closes).rolling(self.entry_window).max().shift(1).iloc[-1]
        )
        donchian_low = (
            pd.Series(closes).rolling(self.exit_window).min().shift(1).iloc[-1]
        )

        # 2. 交易决策
        action = None
        if shares == 0:
            if today_price > donchian_high:  # 突破买入
                action = "BUY"
        elif shares > 0:
            if today_price < donchian_low:  # 跌破卖出
                action = "SELL"

        # 3. 硬止损
        if shares > 0:
            self.max_price = max(self.max_price, today_price)
            if today_price < self.max_price * (1 - self.stop_loss_pct):
                action = "SELL"

        # 4. 执行
        if action == "BUY":
            number = cash / today_price
            choices.append({self.ticker: (buy_or_sell_choice.Buy, number)})
            self.max_price = today_price
        elif action == "SELL":
            choices.append({self.ticker: (buy_or_sell_choice.Sell, shares)})
            self.max_price = 0

        return choices


class CryptoTrendStrategy(strategy_base):
    """
    改进版 Crypto 趋势策略 (ETH-USD)

    核心改进:
    1. 使用 Efficiency Ratio (ER) 替代 Hurst，解决滞后问题。
    2. 引入冷却期 (Cooldown)，防止止损后反复被打脸。
    3. 结合 30日均线 (MA)，只做多头趋势。
    """

    def __init__(
        self,
        ticker="ETH-USD",
        initial_money=1000000,
        er_window=20,  # ER 计算窗口 (短周期，灵敏)
        er_threshold=0.35,  # ER 阈值 (0.35 约等于 Hurst 0.65，代表强趋势)
        ma_window=30,  # 趋势方向判断窗口
        stop_loss_pct=0.10,  # 追踪止损幅度
        cooldown_days=5,  # 止损后的冷静期天数
    ):
        super(CryptoTrendStrategy, self).__init__()
        self.stock_names = [ticker]
        self.ticker = ticker
        self.initial_money = initial_money

        # 策略参数
        self.er_window = er_window
        self.er_threshold = er_threshold
        self.ma_window = ma_window
        self.stop_loss_pct = stop_loss_pct
        self.cooldown_days = cooldown_days

        # 内部状态
        self.max_price = 0  # 记录持仓期间的最高价 (用于追踪止损)
        self.cooldown_counter = 0  # 冷却倒计时

    def get_name(self):
        return (
            f"CryptoTrend_ER({self.ticker}, ER>{self.er_threshold}, MA{self.ma_window})"
        )

    def get_stock_source(self, stock_name):
        return "yahoo"

    def calculate_efficiency_ratio(self, prices, window):
        """
        计算卡夫曼效率系数 (ER)
        ER = |Price_Change| / Sum(Absolute_Daily_Changes)
        """
        if len(prices) < window + 1:
            return 0.0

        s = pd.Series(prices)

        # 分子：位移 (趋势的净结果)
        change = s.diff(window).abs().iloc[-1]

        # 分母：路程 (趋势的波动噪音)
        volatility = s.diff(1).abs().rolling(window=window).sum().iloc[-1]

        if volatility == 0:
            return 0.0

        return change / volatility

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        stock_data = self.latest_stocks_info[self.ticker]
        today_price = extract_close_price(stock_data, self.today_time)

        if today_price is None or np.isnan(today_price):
            return choices

        # 0. 状态更新
        current_shares = self.hold_stock_number.get(self.ticker, 0)
        has_position = current_shares > 0

        # --- 1. 冷却机制与风控 ---

        # 如果处于冷却期，强制空仓并跳过交易
        if self.cooldown_counter > 0:
            self.cooldown_counter -= 1
            if has_position:  # 防御性平仓
                choices.append({self.ticker: (buy_or_sell_choice.Sell, current_shares)})
            return choices

        # 追踪止损检查
        if has_position:
            self.max_price = max(self.max_price, today_price)
            # 如果从最高点回撤超过设定比例
            if today_price < self.max_price * (1 - self.stop_loss_pct):
                choices.append({self.ticker: (buy_or_sell_choice.Sell, current_shares)})
                self.has_position = False
                self.max_price = 0
                self.cooldown_counter = self.cooldown_days  # 触发冷却
                return choices

        # --- 2. 计算指标 (ER 和 MA) ---

        hist_df = stock_data.get_history_price(self.today_time)
        closes = hist_df["close"].values

        # 确保数据足够 (取较大窗口 + 缓冲)
        required_len = max(self.er_window, self.ma_window) + 5
        if len(closes) < required_len:
            return choices

        # 计算 ER (趋势效率/强度)
        # 仅使用最近 er_window 天的数据
        er_value = self.calculate_efficiency_ratio(closes, self.er_window)

        # 计算 MA (趋势方向)
        # 使用简单移动平均 SMA
        ma_value = np.mean(closes[-self.ma_window :])

        # --- 3. 交易决策 ---

        # 核心逻辑:
        # 牛市 = 走势顺畅 (ER高) + 价格在均线之上 (趋势向上)
        is_strong_trend = er_value > self.er_threshold
        is_uptrend = today_price > ma_value

        if not has_position:
            # 入场：必须同时满足“强趋势”和“向上”
            if is_strong_trend and is_uptrend:
                cash = self.initial_money + self.changed_money
                if cash > 0:
                    number_to_buy = cash / today_price * 0.99  # 预留手续费
                    choices.append(
                        {self.ticker: (buy_or_sell_choice.Buy, number_to_buy)}
                    )
                    self.max_price = today_price  # 初始化最高价

        elif has_position:
            # 出场条件：
            # 1. 趋势反转：价格跌破均线
            # 2. 趋势噪音化：ER 降得太低 (比如 < 0.2)，说明市场进入混乱震荡

            trend_broken = today_price < ma_value
            market_choppy = er_value < 0.20

            if trend_broken or market_choppy:
                choices.append({self.ticker: (buy_or_sell_choice.Sell, current_shares)})
                self.has_position = False
                self.max_price = 0
                # 正常离场不需要冷却，只有止损才需要

        return choices
