import numpy as np
import pandas as pd


class CryptoTrendStrategy(strategy_base):
    def __init__(
        self,
        ticker="ETH-USD",
        initial_money=1000000,
        # 优化点 1：缩短窗口
        # Crypto 变化快，用 30 天均线看方向，用 14-20 天看趋势效率
        er_window=20,
        ma_window=30,
        er_threshold=0.35,  # ER > 0.35 通常意味着强趋势 (相当于 Hurst > 0.65)
        stop_loss_pct=0.10,
    ):
        super(CryptoTrendStrategy, self).__init__()
        self.stock_names = [ticker]
        self.ticker = ticker
        self.initial_money = initial_money

        self.er_window = er_window
        self.ma_window = ma_window
        self.er_threshold = er_threshold
        self.stop_loss_pct = stop_loss_pct

        self.max_price = 0
        self.cooldown_counter = 0

    def calculate_efficiency_ratio(self, prices, window):
        """
        计算卡夫曼效率系数 (ER)
        ER = |Change| / Sum(Vol)
        """
        if len(prices) < window + 1:
            return 0.0

        # 转换为 Series 方便计算
        s = pd.Series(prices)

        # 1. 分子：价格的总位移 (Direction)
        change = s.diff(window).abs().iloc[-1]

        # 2. 分母：每一天的波动之和 (Volatility/Noise)
        # 也就是每天涨跌幅绝对值的 rolling sum
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

        current_shares = self.hold_stock_number.get(self.ticker, 0)
        has_position = current_shares > 0

        # --- 冷却与止损逻辑 (保持不变) ---
        if self.cooldown_counter > 0:
            self.cooldown_counter -= 1
            if has_position:
                choices.append({self.ticker: (buy_or_sell_choice.Sell, current_shares)})
            return choices

        if has_position:
            self.max_price = max(self.max_price, today_price)
            if today_price < self.max_price * (1 - self.stop_loss_pct):
                choices.append({self.ticker: (buy_or_sell_choice.Sell, current_shares)})
                self.cooldown_counter = 5
                self.max_price = 0
                return choices

        # --- 核心优化：使用 ER 替代滞后的 Hurst ---

        # 获取足够的数据 (窗口 + 缓冲)
        hist_df = stock_data.get_history_price(self.today_time)
        closes = hist_df["close"].values

        if len(closes) < self.ma_window + 5:
            return choices

        # 1. 计算 ER (替代 Hurst)
        # 用最近 20 天的数据计算，反应速度比 100 天的 Hurst 快 5 倍
        er_value = self.calculate_efficiency_ratio(closes, self.er_window)

        # 2. 计算均线 (判断方向)
        ma_trend = np.mean(closes[-self.ma_window :])

        # --- 信号判定 ---

        # 核心逻辑：
        # ER 高 = 趋势非常“顺畅” (噪音少，资金合力强)
        # 价格 > 均线 = 趋势向上

        is_efficient_trend = er_value > self.er_threshold
        is_bullish = today_price > ma_trend

        if not has_position:
            # 只有当“走势很干净”且“向上”时买入
            if is_efficient_trend and is_bullish:
                cash = self.initial_money + self.changed_money
                number = cash / today_price * 0.99
                if number > 0:
                    choices.append({self.ticker: (buy_or_sell_choice.Buy, number)})
                    self.max_price = today_price

        elif has_position:
            # 出场：
            # 1. 均线破坏 (Trend Broken)
            # 2. ER 骤降 (Trend becomes Choppy/Noisy) -> 变成震荡市，落袋为安

            trend_broken = today_price < ma_trend
            market_choppy = er_value < 0.20  # 趋势效率太低，全是噪音

            if trend_broken or market_choppy:
                choices.append({self.ticker: (buy_or_sell_choice.Sell, current_shares)})
                self.max_price = 0

        return choices
