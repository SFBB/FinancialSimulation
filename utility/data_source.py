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

    def _get_data_range(self):
        if self.data is None or self.data.empty:
            return None, None
        return self.data.index.min(), self.data.index.max()

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

            min_date, max_date = self._get_data_range()

            if min_date is not None and max_date is not None:
                min_date = pd.Timestamp(min_date)
                max_date = pd.Timestamp(max_date)

                # Ensure timezone-naive for comparison with req_start/req_end which are naive
                if min_date.tzinfo is not None:
                    min_date = min_date.tz_localize(None)
                if max_date.tzinfo is not None:
                    max_date = max_date.tz_localize(None)

                if min_date <= req_start and max_date >= (
                    req_end - dt.timedelta(days=4)
                ):
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

    def _get_data_range(self):
        if self.data is None or self.data.empty:
            return None, None
        _, min_date = self.data.index.min()
        _, max_date = self.data.index.max()
        return min_date, max_date

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

    def _get_data_range(self):
        if self.data is None or self.data.empty:
            return None, None
        _, min_date = self.data.index.min()
        _, max_date = self.data.index.max()
        return min_date, max_date

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
            
            # --- Fetch Valuation Data (PE/PB) ---
            try:
                # stock_a_indicator_lg: symbol="600519"
                # Columns: trade_date, pe, pe_ttm, pb, ps, pcf
                val_data = ak.stock_a_indicator_lg(symbol=symbol)
                
                if not val_data.empty:
                    # Rename to standard
                    val_data.rename(columns={"trade_date": "date"}, inplace=True)
                    val_data["date"] = pd.to_datetime(val_data["date"])
                    val_data.set_index("date", inplace=True)
                    
                    # Ensure indices are aligned (tz-naive)
                    if self.data.index.tz is not None:
                         self.data.index = self.data.index.tz_localize(None)
                    
                    # Merge PE/PE_TTM into self.data
                    # We use left join to keep price data structure
                    cols_to_merge = [c for c in ["pe", "pe_ttm"] if c in val_data.columns]
                    if cols_to_merge:
                        self.data = self.data.join(val_data[cols_to_merge], how="left")
                        # Forward fill valuation data for missing days (if any)
                        self.data[cols_to_merge] = self.data[cols_to_merge].ffill()

            except Exception as e:
                print(f"AKShare Valuation fetch failed for {self.data_name} (non-critical): {e}")
                # Continue without PE
                pass

        except Exception as e:
            print(f"AKShare fetch failed for {self.data_name}: {e}")
            self.data = pd.DataFrame()
            raise e


class YahooFinanceDataSource(TimeRangedDataSourceBase):
    def __init__(
        self,
        data_name: str,
        start_time: dt.datetime,
        end_time: dt.datetime,
        interval: dt.timedelta = dt.timedelta(days=1),
        cache_dir="cache",
    ):
        super().__init__(
            data_name, "yahoo_finance", start_time, end_time, interval, cache_dir
        )
        self.stock = None

    def _download_data(self):
        import yfinance as yf

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
                self.stock = yf.Ticker(self.data_name)
            except Exception as e:
                print(f"Failed to init yahoo finance ticker for {self.data_name}: {e}")
                self.data = DataFrame()
                raise e
        if self.stock:
            try:
                # Always fetch max history to ensure cache covers potential start dates
                self.data = self.stock.history(
                    period="max",
                    interval=interval_str,
                    actions=True  # Explicitly request Dividends and Splits
                )
                
                # Ensure index name is 'date' for stock_util compatibility
                self.data.index.name = "date"
                
                # --- Calculate PE (Approximate) ---
                try:
                    # Get financials (quarterly)
                    # Note: yfinance financials often only go back 4 years.
                    # For longer history, this method is limited, but better than nothing.
                    fin = self.stock.quarterly_financials
                    if fin is not None and not fin.empty:
                        # Row 'Basic EPS' or 'Diluted EPS'
                        # Transpose so index is Date
                        fin_T = fin.T
                        
                        eps_col = None
                        for c in ["Basic EPS", "Diluted EPS"]:
                            if c in fin_T.columns:
                                eps_col = c
                                break
                        
                        if eps_col:
                            eps_series = fin_T[eps_col].sort_index()
                            # Convert to numeric
                            eps_series = pd.to_numeric(eps_series, errors='coerce')
                            # Ensure Index is Datetime
                            eps_series.index = pd.to_datetime(eps_series.index)
                            
                            if not eps_series.empty:
                                # Reindex to daily price index
                                # Ensure timezone naive alignment
                                if self.data.index.tz is not None:
                                    price_idx = self.data.index.tz_localize(None)
                                else:
                                    price_idx = self.data.index
                                
                                # Ensure EPS index is also naive
                                if eps_series.index.tz is not None:
                                    eps_series.index = eps_series.index.tz_localize(None)
                                else:
                                    # If eps_series is already naive but price_idx was just converted, we are good.
                                    pass
                                    
                                # Expand quarterly EPS to daily
                                # We assume EPS is known on the report date (approx)
                                # ffill() propagates it forward
                                daily_eps = eps_series.reindex(price_idx, method='ffill')
                                
                                # Calculate PE = Close / EPS
                                # Use Rolling TTM EPS (Sum of last 4 quarters)?
                                # Simplifying: Just use the latest Quarterly EPS * 4 (Annualized approximation)
                                # Or if EPS is already annual? No, quarterly_financials is quarterly.
                                annual_eps = daily_eps * 4
                                
                                self.data['pe_ttm'] = self.data['Close'] / annual_eps
                                
                                # Handle negative PE or infinite (usually filtered or kept as is)
                                # self.data['pe_ttm'] = self.data['pe_ttm'].where(self.data['pe_ttm'] > 0)
                                
                except Exception as e:
                    print(f"Yahoo Finance PE calc failed for {self.data_name} (non-critical): {e}")

            except Exception as e:
                print(f"Yahoo Finance fetch failed for {self.data_name}: {e}")
                self.data = DataFrame()
                raise e


class LocalCSVDataSource(TimeRangedDataSourceBase):
    def __init__(
        self,
        data_name: str, # This will be the file path
        start_time: dt.datetime,
        end_time: dt.datetime,
        interval: dt.timedelta = dt.timedelta(days=1),
        cache_dir="cache",
    ):
        # source_name="local"
        super().__init__(
            data_name, "local", start_time, end_time, interval, cache_dir
        )

    def _download_data(self):
        # Here "download" means read from local file
        try:
            # Assume data_name is the file path
            file_path = self.data_name
            if not os.path.exists(file_path):
                print(f"Local file not found: {file_path}")
                self.data = pd.DataFrame()
                return

            df = pd.read_csv(file_path)
            
            # Smart Index Detection
            # Try to find a column that looks like a Date
            date_col = None
            for col in df.columns:
                if col.lower() in ["date", "time", "trade_date", "日期", "datetime"]:
                    date_col = col
                    break
            
            if date_col:
                df[date_col] = pd.to_datetime(df[date_col])
                df.set_index(date_col, inplace=True)
                df.index.name = "date"
            else:
                # If no date column, maybe index is already date?
                try:
                    df.index = pd.to_datetime(df.index)
                    df.index.name = "date"
                except:
                    print(f"Could not identify Date column/index in {file_path}")
                    self.data = pd.DataFrame()
                    return

            # Normalize Columns (Lower case)
            df.columns = [c.lower().strip() for c in df.columns]
            
            # Ensure timezone naive
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
                
            self.data = df.sort_index()
            
        except Exception as e:
            print(f"Failed to read local CSV {self.data_name}: {e}")
            self.data = pd.DataFrame()
            raise e
