import csv
import datetime
import pandas as pd
import yahooquery

from utility import math_util, stock_analysis
from utility.strategy import strategy_base, MarketConfig, buy_or_sell_choice, extract_close_price


class MoutaiStrategy(strategy_base):
    """
    A simple trend-following strategy for Kweichow Moutai (600519.SS).
    Demonstrates:
    - A-Share T+1 Settlement (CN_Market)
    - Stamp Duty (Tax on Sell)
    """

    def __init__(self, fast_ma=5, slow_ma=20, stop_loss_pct=0.08):
        # Initialize with CN Market Config!
        super(MoutaiStrategy, self).__init__(MarketConfig.CN_Market())
        
        self.stock_names = ["600519.SS"]
        self.initial_money = 1000000
        self.fast_ma = fast_ma
        self.slow_ma = slow_ma
        self.stop_loss_pct = stop_loss_pct
        
        self.has_invested = False
        self.purchase_price = 0

    def get_name(self):
        return f"MoutaiStrategy(Momentum+RiskMgmt)"

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        today_price = extract_close_price(
            self.latest_stocks_info["600519.SS"], self.today_time
        )
        if today_price is None:
            return choices

        history = self.latest_stocks_info["600519.SS"].get_history_price(self.today_time)
        close_prices = history["close"]

        # Ensure enough data for indicators (MACD=26 + padding)
        if len(close_prices) < 30:
            return choices

        # Technical Indicators
        # 1. Trend (MA)
        fast_ma_series = stock_analysis.get_moving_average(close_prices, self.fast_ma)
        slow_ma_series = stock_analysis.get_moving_average(close_prices, self.slow_ma)
        curr_fast = fast_ma_series.iloc[-1]
        curr_slow = slow_ma_series.iloc[-1]
        
        # 2. Momentum (MACD)
        macd, signal, hist = stock_analysis.get_macd(close_prices)
        curr_hist = hist.iloc[-1]
        prev_hist = hist.iloc[-2] if len(hist) > 1 else 0
        
        # 3. Strength (RSI)
        rsi = stock_analysis.get_rsi(close_prices)
        curr_rsi = rsi.iloc[-1]

        # 1. Management of Existing Position
        if self.has_invested:
             sell_signal = False
             reason = ""
             
             # Condition A: Hard Stop Loss (8%)
             if today_price < self.purchase_price * (1 - self.stop_loss_pct):
                 sell_signal = True
                 reason = "Stop Loss"
             
             # Condition B: Trend Reversal (MACD Crosses Down)
             elif curr_hist < 0 and prev_hist > 0:
                 sell_signal = True
                 reason = "MACD Cross Down"
                 
             # Condition C: MA Death Cross (Secondary)
             elif curr_fast < curr_slow:
                 sell_signal = True
                 reason = "MA Death Cross"

             if sell_signal:
                 shares_to_sell = self.hold_stock_number.get("600519.SS", 0)
                 if shares_to_sell > 0:
                     choices.append(
                        {"600519.SS": (buy_or_sell_choice.Sell, shares_to_sell)}
                     )
                     self.has_invested = False
                     self.purchase_price = 0
                     # print(f"SELL ({reason}) at {today_price:.2f} | RSI: {curr_rsi:.1f}")
                     return choices

        # 2. Entry Logic (Buy)
        if not self.has_invested:
            # Condition A: Trend Alignment (Fast > Slow)
            if curr_fast > curr_slow:
                # Condition B: Momentum (MACD Histogram Positive & Rising)
                if curr_hist > 0:
                    # Condition C: Not Overbought (RSI < 70)
                    if curr_rsi < 70:
                        
                        # Size: 40% of Capital (Risk Management)
                        current_equity = self.initial_money + self.changed_money
                        invest_amount = current_equity * 0.4
                        number = invest_amount / today_price
                        
                        choices.append({"600519.SS": (buy_or_sell_choice.Buy, number)})
                        self.has_invested = True
                        self.purchase_price = today_price
                        # print(f"BUY at {today_price:.2f} | RSI: {curr_rsi:.1f} | Hist: {curr_hist:.2f}")

        return choices

    def end(self):
        records = self.__investments_info__.get_records()
        with open(f"records_{self.get_name()}.csv", "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "time",
                    "price",
                    "choice",
                    "money_value",
                    "number",
                    "delta_money_value",
                    "delta_number",
                    "cost"
                ]
            )
            for record in records:
                writer.writerow(
                    [
                        record["time"],
                        record["price"],
                        int(record["choice"]),
                        record["money_value"],
                        record["number"],
                        record["delta_money_value"],
                        record["delta_number"],
                        record["cost"]
                    ]
                )

        self.print_performance_report()
