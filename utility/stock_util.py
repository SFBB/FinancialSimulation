import datetime
from .data_source import YahooQueryDataSource, AKShareDataSource
import os
from abc import ABC, abstractmethod
from enum import Enum

import pandas as pd
from yahooquery import Ticker

try:
    import akshare as ak
except ImportError:
    ak = None


class buy_or_sell_choice(Enum):
    Buy = 0, "Buy"
    Sell = 1, "Sell"
    DoNothing = 2, "DoNothing"

    def __new__(cls, value, name):
        member = object.__new__(cls)
        member._value_ = value
        member.fullname = name
        return member

    def __int__(self):
        return self.value


class stock(Ticker):
    def __init__(self, symbols, **kwargs):
        super(stock, self).__init__(symbols, **kwargs)
        self.symbols = symbols

    def get_hurst_exponent(self):
        pass

    def current_judgement(self):
        pass


class stock_info:
    def __init__(
        self,
        ticket_name,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        interval: datetime.timedelta,
        source: str = "yahoo",  # "yahoo" or "akshare"
    ):
        self.ticket_name = ticket_name
        self.start_time = start_time - datetime.timedelta(
            days=365
        )  # Fetch extra year for safety
        self.end_time = end_time
        self.interval = interval
        self.source = source.lower()
        self.stock = None  # Lazy load only when needed to fetch
        self.raw_data = pd.DataFrame()  # Original data from source
        self.history_price_data = pd.DataFrame()  # Core data for simulation

    def __normalize_data(self):
        if self.raw_data.empty:
            return

        df = self.raw_data.copy()

        # 1. Standardize Index to Datetime
        if self.source == "yahoo":
            df = df.reset_index()
            if "date" in df.columns:
                df["date"] = (
                    pd.to_datetime(df["date"], utc=True, format="mixed")
                    .dt.tz_convert(None)
                    .dt.normalize()
                )
                df = df.set_index("date")

        elif self.source == "akshare":
            if "日期" in df.columns:
                df["date"] = pd.to_datetime(df["日期"]).dt.normalize()
                df = df.set_index("date")

            column_map = {
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
            }
            df = df.rename(columns=column_map)

        # 2. Filter/Select Core Columns
        core_cols = ["open", "close", "high", "low", "volume"]
        available_cols = [c for c in core_cols if c in df.columns]
        # self.history_price_data will be OVERWRITTEN here based on self.raw_data
        # This is correct for the 'freshly fetched' part, but we need to ensure update_cache merges it.
        self.history_price_data = df[available_cols].sort_index()

    def initialize(self):
        if self.source == "yahoo":
            data_source = YahooQueryDataSource(
                self.ticket_name, self.start_time, self.end_time, self.interval
            )
            data_source.initialize()
            self.raw_data = data_source.data
        elif self.source == "akshare":
            data_source = AKShareDataSource(
                self.ticket_name, self.start_time, self.end_time, self.interval
            )
            data_source.initialize()
            self.raw_data = data_source.data

        self.__normalize_data()

        # Finally, slice the data to the specific requested range for this simulation instance
        # This ensures the simulation only sees what it asked for, even if cache is huge
        if not self.history_price_data.empty:
            mask = (
                self.history_price_data.index >= pd.Timestamp(self.start_time.date())
            ) & (self.history_price_data.index <= pd.Timestamp(self.end_time.date()))
            self.history_price_data = self.history_price_data.loc[mask]

    def get_today_price(self, current_time: datetime.datetime) -> pd.DataFrame:
        target_date = pd.Timestamp(current_time.date())
        return self.history_price_data.loc[
            self.history_price_data.index.get_level_values("date") == target_date
        ]

    def get_history_price(self, current_time: datetime.datetime):
        target_date = pd.Timestamp(current_time.date())
        return self.history_price_data.loc[
            self.history_price_data.index.get_level_values("date") <= target_date
        ]


def extract_close_price(stock_info: stock_info, date_time: datetime.datetime):
    if len(stock_info.get_today_price(date_time).close.values) > 0:
        return stock_info.get_today_price(date_time).close.values[0]
    return None


def extract_open_price(stock_info: stock_info, date_time: datetime.datetime):
    if len(stock_info.get_today_price(date_time).close.values) > 0:
        df = stock_info.get_today_price(date_time)
        if "open" in df.columns:
            return df["open"].values[0]
        # Fallback to close if no open (unlikely)
        return df["close"].values[0]
    return None


def extract_volume(stock_info: stock_info, date_time: datetime.datetime):
    if len(stock_info.get_today_price(date_time).close.values) > 0:
        # Check if 'volume' column exists
        df = stock_info.get_today_price(date_time)
        if "volume" in df.columns:
            return df["volume"].values[0]
    return 0


class promise_base(ABC):
    def __init__(
        self,
        promise_price: float,
        promise_datetime: datetime.datetime,
        stock: stock_info,
        ticket_name: str,
        number: float,
    ):
        self.promise_price = promise_price
        self.promise_datetime = promise_datetime
        self.stock = stock
        self.ticket_name = ticket_name
        self.number = number

    @abstractmethod
    def do_promise_or_not(
        self, current_datetime: datetime.datetime
    ) -> tuple[bool, buy_or_sell_choice]:
        return False, buy_or_sell_choice.DoNothing


class promise_buy(promise_base):
    def __init__(
        self,
        promise_price: float,
        promise_datetime: datetime.datetime,
        stock: stock_info,
        ticket_name: str,
        number: float,
    ):
        super(promise_buy, self).__init__(
            promise_price, promise_datetime, stock, ticket_name, number
        )

    def do_promise_or_not(
        self, current_datetime: datetime.datetime
    ) -> tuple[bool, buy_or_sell_choice]:
        if current_datetime > self.promise_datetime:
            return True, buy_or_sell_choice.Buy
        today_price = extract_close_price(self.stock, current_datetime)
        if today_price == None:
            return False, buy_or_sell_choice.DoNothing
        elif today_price <= self.promise_price:
            return True, buy_or_sell_choice.Buy
        return False, buy_or_sell_choice.DoNothing


class promise_sell(promise_base):
    def __init__(
        self,
        promise_price: float,
        promise_datetime: datetime.datetime,
        stock: stock_info,
        ticket_name: str,
        number: float,
    ):
        super(promise_sell, self).__init__(
            promise_price, promise_datetime, stock, ticket_name, number
        )

    def do_promise_or_not(
        self, current_datetime: datetime.datetime
    ) -> tuple[bool, buy_or_sell_choice]:
        if current_datetime > self.promise_datetime:
            return True, buy_or_sell_choice.Sell
        today_price = extract_close_price(self.stock, current_datetime)
        if today_price == None:
            return False, buy_or_sell_choice.DoNothing
        elif today_price >= self.promise_price:
            return True, buy_or_sell_choice.Sell
        return False, buy_or_sell_choice.DoNothing


if __name__ == "__main__":
    si = stock_info(
        "GOOGL",
        datetime.datetime(2012, 12, 12),
        datetime.datetime.now(),
        datetime.timedelta(days=1),
    )
    si.initialize()
    print(si.get_today_price(datetime.datetime.now()))
