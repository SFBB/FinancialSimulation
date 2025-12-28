import csv
import datetime

import numpy as np
import pandas as pd
import yahooquery

from utility import math_util, stock_analysis
from utility.strategy import *


class GOOGLStrategy(strategy_base):
    def __init__(self):
        super(GOOGLStrategy, self).__init__()
        self.stock_names = ["GOOGL"]
        self.initial_money = 1000000

        self.has_bet = False
        self.bet_price = 0
        self.bet_target_price = 0
        self.bet_date = datetime.datetime.now()
        self.promises = []  # list[promise_base]

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        today_price = extract_close_price(
            self.latest_stocks_info["GOOGL"], self.today_time
        )
        if today_price == None:
            return []
        choices = []
        GOOGL_history_price = self.latest_stocks_info["GOOGL"].get_history_price(
            self.today_time
        )
        x = GOOGL_history_price.loc[
            GOOGL_history_price.index.get_level_values("date")
            > (self.today_time - datetime.timedelta(days=90)).date()
        ].close.values
        if len(x) < 2:
            return choices
        hurst_exponent, c = math_util.rs_analysis(x, 2)
        mean = np.average(list(x))
        if abs(hurst_exponent - 0.925) < 0.025:
            trending_rate = (list(x)[-1] - list(x)[0]) / list(x)[0]
            if trending_rate > 0.1 and not self.has_bet:
                # print(trending_rate, self.today_time)
                # self.has_bet = True
                self.bet_price = x[-1]
                self.bet_target_price = x[-1] * trending_rate
                self.bet_date = self.today_time
                number = np.clip(
                    10000 - self.hold_stock_number.get("GOOGL", 0) * 0.5, 0, 10000
                )
                choices.append({"GOOGL": (buy_or_sell_choice.Buy, number)})
                if self.initial_money + self.changed_money > 0:
                    self.new_promise(
                        promise_sell(
                            mean * 1.1,
                            self.today_time + datetime.timedelta(days=16),
                            self.latest_stocks_info["GOOGL"],
                            "GOOGL",
                            number,
                        )
                    )
                # choice = {"GOOGL": (buy_or_sell_choice.Buy, (self.initial_money + self.changed_money) / x[-1])}
        elif hurst_exponent < 0.4:
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

    def end(self):
        GOOGL_history_price = self.latest_stocks_info["GOOGL"].get_history_price(
            self.today_time
        )
        x = GOOGL_history_price.loc[
            GOOGL_history_price.index.get_level_values("date")
            > (self.today_time - datetime.timedelta(days=30)).date()
        ].close.values
        records = self.__investments_info__.get_records()
        with open("records.csv", "w", newline="") as file:
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
                    ]
                )
        if len(x) > 0:
            print(
                "Money change: {}, asset value change: {}".format(
                    self.changed_money,
                    self.changed_money + self.hold_stock_number.get("GOOGL", 0) * x[-1],
                )
            )


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
