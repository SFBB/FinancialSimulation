import datetime
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

    def __get_cache_path(self) -> str:
        return "cache/{}_{}_{}.pkl".format(
            self.ticket_name,
            self.source,
            self.interval.days,
        )

    def __has_cache(self):
        return os.path.exists(self.__get_cache_path())

    def __load_cache(self):
        try:
            data = pd.read_pickle(self.__get_cache_path())
            if isinstance(data, tuple) and len(data) == 2:
                self.raw_data, self.history_price_data = data
            else:
                # Backward compatibility or fallback
                self.history_price_data = data
                self.raw_data = pd.DataFrame()
                self.__normalize_data()  # Try to reconstruct if possible, or just fail over
        except Exception:
            self.update()

    def __update_cache(self):
        if not os.path.exists("cache"):
            os.makedirs("cache")

        # Load existing cache to merge
        existing_raw = pd.DataFrame()
        existing_price = pd.DataFrame()
        if self.__has_cache():
            try:
                data = pd.read_pickle(self.__get_cache_path())
                if isinstance(data, tuple) and len(data) == 2:
                    existing_raw, existing_price = data
                else:
                    existing_price = data
            except:
                pass

        # Merge new data with existing
        # Concat and remove duplicates based on index (Date)
        if not self.raw_data.empty:
            if not existing_raw.empty:
                full_raw = pd.concat([existing_raw, self.raw_data])
                # Deduplicate by index
                full_raw = full_raw[~full_raw.index.duplicated(keep="last")]
                self.raw_data = full_raw.sort_index()
            # If existing is empty, self.raw_data is already set
        else:
            self.raw_data = existing_raw  # Keep existing if fetch failed

        if not self.history_price_data.empty:
            if not existing_price.empty:
                full_price = pd.concat([existing_price, self.history_price_data])
                full_price = full_price[~full_price.index.duplicated(keep="last")]
                self.history_price_data = full_price.sort_index()
            # If existing is empty, self.history_price_data is already set
        else:
            self.history_price_data = existing_price

        # Save merged data
        if not self.history_price_data.empty:
            pd.to_pickle(
                (self.raw_data, self.history_price_data), self.__get_cache_path()
            )

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
        coverage_complete = False
        if self.__has_cache():
            try:
                self.__load_cache()
                # Check Coverage
                if not self.history_price_data.empty:
                    min_date = self.history_price_data.index.min().to_pydatetime()
                    max_date = self.history_price_data.index.max().to_pydatetime()

                    # We only care if we have data covering the requested range
                    # Note: We compare Dates strictly (ignoring time for daily resolution cache)
                    req_start = pd.Timestamp(self.start_time.date())
                    req_end = pd.Timestamp(self.end_time.date())

                    # Convert min/max from index (Timestamp) directly
                    min_date = self.history_price_data.index.min()
                    max_date = self.history_price_data.index.max()

                    if min_date <= req_start and max_date >= (
                        req_end - datetime.timedelta(days=4)
                    ):
                        coverage_complete = True
            except Exception as e:
                print(f"Failed to load cache for {self.ticket_name}: {e}")
                # Fallthrough to update

        if not coverage_complete:
            print(f"Cache miss or partial for {self.ticket_name}. Fetching...")
            self.update()

        # Finally, slice the data to the specific requested range for this simulation instance
        # This ensures the simulation only sees what it asked for, even if cache is huge
        if not self.history_price_data.empty:
            mask = (
                self.history_price_data.index >= pd.Timestamp(self.start_time.date())
            ) & (self.history_price_data.index <= pd.Timestamp(self.end_time.date()))
            self.history_price_data = self.history_price_data.loc[mask]

    # update stock info
    def update(self):
        if self.source == "yahoo":
            self.__update_from_yahoo()
        elif self.source == "akshare":
            self.__update_from_akshare()
        else:
            print(f"Unknown source: {self.source}")

        self.__normalize_data()
        self.__update_cache()

    def __update_from_yahoo(self):
        interval = "1d"
        if self.interval.days > 0:
            interval = "{}d".format(self.interval.days)
        elif self.interval.seconds > 0:
            interval = "{}h".format(self.interval.seconds // 60 // 60)

        # Lazy init
        if self.stock is None:
            try:
                self.stock = stock(self.ticket_name)
            except Exception as e:
                print(f"Failed to init yahoo ticker for {self.ticket_name}: {e}")
                self.raw_data = pd.DataFrame()
                return

        if self.stock:
            try:
                # Store in raw_data
                self.raw_data = self.stock.history(
                    "100y", interval, None, self.end_time
                )
            except Exception as e:
                print(f"Yahoo fetch failed for {self.ticket_name}: {e}")
                self.raw_data = pd.DataFrame()

    def __update_from_akshare(self):
        if ak is None:
            print("AKShare not installed.")
            return

        # Start/End date formatting "YYYYMMDD"
        # AKShare usually expects strings.
        # stock_zh_a_hist: code='000001', period='daily', start_date='20170301', end_date='20210907', adjust='qfq'
        start_str = self.start_time.strftime("%Y%m%d")
        end_str = self.end_time.strftime("%Y%m%d")

        try:
            # Assuming ticket_name is a valid code like "000001"
            symbol = self.ticket_name
            # Minimal cleaning if user passed "sh600519" -> "600519"
            if not symbol.isdigit():
                # Simple heuristic: extract digits
                symbol = "".join(filter(str.isdigit, symbol))

            self.raw_data = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date="19000101",  # Fetch all available history
                end_date=end_str,
                adjust="qfq",
            )
        except Exception as e:
            print(f"AKShare fetch failed for {self.ticket_name}: {e}")
            self.raw_data = pd.DataFrame()

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
