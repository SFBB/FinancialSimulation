import os
from abc import ABC, abstractmethod
import pandas as pd
import datetime as dt
from pandas import DataFrame
from scipy.sparse import data


class DataSourceBase(ABC):
    def __init__(self, data_name: str, source_name: str, cache_dir="cache"):
        self.data_name = data_name
        self.source_name = source_name
        self.cache_dir = cache_dir
        self.data = DataFrame()

    def initialize(self):
        self._load_data()

    def _get_cache_path(self) -> str:
        return os.path.join(
            self.cache_dir, f"{self.source_name}_{self.data_name}_cache.pkl"
        )

    def _has_cache(self) -> bool:
        return os.path.exists(self._get_cache_path())

    def _load_data(self):
        if self._has_cache():
            try:
                self._load_cache()
            except Exception as e:
                print(f"Failed to load cache: {e}, redownloading data.")
                try:
                    self._download_data()
                except Exception as e2:
                    print(f"Failed to download data: {e2}")
                    raise e2
                self._update_cache()
        else:
            try:
                self._download_data()
            except Exception as e:
                print(f"Failed to download data: {e}")
                raise e
            self._update_cache()

    def _load_cache(self):
        self.data = pd.read_pickle(self._get_cache_path())

    def _update_cache(self):
        pd.to_pickle(self.data, self._get_cache_path())

    @abstractmethod
    def _download_data(self):
        pass


class TimeRangedDataSourceBase(DataSourceBase):
    """We assume self.data is a data frame with time range."""

    def __init__(
        self,
        data_name: str,
        source_name: str,
        start_time: dt.datetime,
        end_time: dt.datetime,
        interval: dt.timedelta,
        cache_dir="cache",
    ):
        super().__init__(data_name, source_name, cache_dir)
        self.start_time = start_time
        self.end_time = end_time
        self.interval = interval

    def _get_cache_path(self) -> str:
        return os.path.join(
            self.cache_dir,
            f"{self.source_name}_{self.data_name}_cache_{self.interval.days}.pkl",
        )

    def _load_data(self):
        if self._has_cache():
            try:
                self._load_cache()
            except Exception as e:
                print(f"Failed to load cache: {e}, redownloading data.")
                try:
                    self._download_data()
                except Exception as e2:
                    print(f"Failed to download data: {e2}")
                    raise e2
                self._update_cache()
            # we try to detect whether the time range is in the cache or not
            range_complete = False

            # We only care if we have data covering the requested range
            # Note: We compare Dates strictly (ignoring time for daily resolution cache)
            req_start = pd.Timestamp(self.start_time.date())
            req_end = pd.Timestamp(self.end_time.date())

            # Convert min/max from index (Timestamp) directly
            _, min_date = self.data.index.min()
            _, max_date = self.data.index.max()
            min_date = pd.Timestamp(min_date)
            max_date = pd.Timestamp(max_date)

            if min_date <= req_start and max_date >= (req_end - dt.timedelta(days=4)):
                range_complete = True

            if not range_complete:
                print(f"Cache miss or partial for {self.data_name}. Fetching...")
                try:
                    self._download_data()
                except Exception as e:
                    print(f"Failed to download data: {e}")
                    raise e
                self._update_cache()
        else:
            try:
                self._download_data()
            except Exception as e:
                print(f"Failed to download data: {e}")
                raise e
            self._update_cache()


class YahooQueryDataSource(TimeRangedDataSourceBase):
    def __init__(
        self,
        data_name: str,
        start_time: dt.datetime,
        end_time: dt.datetime,
        interval: dt.timedelta = dt.timedelta(days=1),
        cache_dir="cache",
    ):
        super().__init__(
            data_name, "yahoo_query", start_time, end_time, interval, cache_dir
        )
        self.stock = None

    def _download_data(self):
        from yahooquery import Ticker

        interval_str = "1d"
        if self.interval >= dt.timedelta(weeks=1):
            interval_str = "1wk"
        elif self.interval >= dt.timedelta(days=1):
            interval_str = "1d"
        elif self.interval >= dt.timedelta(hours=1):
            interval_str = "1h"
        else:
            interval_str = "15m"

        if self.stock is None:
            try:
                self.stock = Ticker(self.data_name)
            except Exception as e:
                print(f"Failed to init yahoo ticker for {self.data_name}: {e}")
                self.data = DataFrame()
                raise e
        if self.stock:
            try:
                self.data = self.stock.history(
                    "100y", interval_str, None, self.end_time
                )
            except Exception as e:
                print(f"Yahoo fetch failed for {self.data_name}: {e}")
                self.data = DataFrame()
                raise e


class AKShareDataSource(TimeRangedDataSourceBase):
    def __init__(
        self,
        data_name: str,
        start_time: dt.datetime,
        end_time: dt.datetime,
        interval: dt.timedelta = dt.timedelta(days=1),
        cache_dir="cache",
    ):
        super().__init__(
            data_name, "AKShare", start_time, end_time, interval, cache_dir
        )
        self.stock = None

    def _download_data(self):
        try:
            import akshare as ak
        except ImportError:
            ak = None

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
            symbol = self.data_name
            # Minimal cleaning if user passed "sh600519" -> "600519"
            if not symbol.isdigit():
                # Simple heuristic: extract digits
                symbol = "".join(filter(str.isdigit, symbol))

            self.data = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date="19000101",  # Fetch all available history
                end_date=end_str,
                adjust="qfq",
            )
        except Exception as e:
            print(f"AKShare fetch failed for {self.data_name}: {e}")
            self.data = pd.DataFrame()
            raise e
