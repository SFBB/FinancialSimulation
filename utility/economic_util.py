import datetime
from abc import ABC, abstractmethod
from .data_source import YahooFinanceDataSource


class economic_info_base(ABC):
    def __init__(
        self,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        interval: datetime.timedelta,
    ):
        self.start_time = start_time
        self.end_time = end_time
        self.interval = interval

    @abstractmethod
    def initialize(self):
        pass

    @abstractmethod
    def update(self):
        pass

    @abstractmethod
    def get_today_info(self, current_time: datetime.datetime):
        pass

    @abstractmethod
    def get_history_info(
        self, current_time: datetime.datetime, time_range: datetime.timedelta
    ):
        pass


class oil_info(economic_info_base):
    def __init__(
        self,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        interval: datetime.timedelta,
    ):
        super().__init__(start_time, end_time, interval)
        self.oil_data = None

    def initialize(self):
        self.oil_data = YahooFinanceDataSource(
            "CL=F", self.start_time, self.end_time, self.interval
        )
        self.oil_data.initialize()

    def update(self):
        if self.oil_data:
            self.oil_data.initialize()

    def get_today_info(self, current_time: datetime.datetime):
        if self.oil_data is None or self.oil_data.data.empty:
            return None
        
        target_date = current_time.date()
        mask = self.oil_data.data.index.date == target_date
        df_today = self.oil_data.data[mask]
        
        if not df_today.empty:
            return df_today.iloc[0]
        return None

    def get_history_info(
        self, current_time: datetime.datetime, time_range: datetime.timedelta
    ):
        if self.oil_data is None or self.oil_data.data.empty:
            return None

        start_time = current_time - time_range
        tz = self.oil_data.data.index.tz
        if tz is not None:
             if start_time.tzinfo is None:
                 start_time = start_time.replace(tzinfo=tz) 
             if current_time.tzinfo is None:
                 current_time = current_time.replace(tzinfo=tz)

        return self.oil_data.data.loc[start_time:current_time]


class us_debt_info(economic_info_base):
    def __init__(
        self,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        interval: datetime.timedelta,
    ):
        super().__init__(start_time, end_time, interval)
        self.debt_data = None

    def initialize(self):
        # ^TNX: CBOE Interest Rate 10 Year T Note
        self.debt_data = YahooFinanceDataSource(
            "^TNX", self.start_time, self.end_time, self.interval
        )
        self.debt_data.initialize()

    def update(self):
        if self.debt_data:
            self.debt_data.initialize()

    def get_today_info(self, current_time: datetime.datetime):
        if self.debt_data is None or self.debt_data.data.empty:
            return None
        
        target_date = current_time.date()
        mask = self.debt_data.data.index.date == target_date
        df_today = self.debt_data.data[mask]
        
        if not df_today.empty:
            return df_today.iloc[0]
        return None

    def get_history_info(
        self, current_time: datetime.datetime, time_range: datetime.timedelta
    ):
        if self.debt_data is None or self.debt_data.data.empty:
            return None

        start_time = current_time - time_range
        tz = self.debt_data.data.index.tz
        if tz is not None:
             if start_time.tzinfo is None:
                 start_time = start_time.replace(tzinfo=tz)
             if current_time.tzinfo is None:
                 current_time = current_time.replace(tzinfo=tz)

        return self.debt_data.data.loc[start_time:current_time]


class cny_rate_info(economic_info_base):
    """
    USD/CNY Exchange Rate Info.
    Ticker: CNY=X
    Rising means CNY depreciation (Bad for A-shares).
    Falling means CNY appreciation (Good for A-shares).
    """
    def __init__(
        self,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        interval: datetime.timedelta,
    ):
        super().__init__(start_time, end_time, interval)
        self.cny_data = None

    def initialize(self):
        self.cny_data = YahooFinanceDataSource(
            "CNY=X", self.start_time, self.end_time, self.interval
        )
        self.cny_data.initialize()

    def update(self):
        if self.cny_data:
            self.cny_data.initialize()

    def get_today_info(self, current_time: datetime.datetime):
        if self.cny_data is None or self.cny_data.data.empty:
            return None
        
        target_date = current_time.date()
        mask = self.cny_data.data.index.date == target_date
        df_today = self.cny_data.data[mask]
        if not df_today.empty:
            return df_today.iloc[0]
        return None

    def get_history_info(
        self, current_time: datetime.datetime, time_range: datetime.timedelta
    ):
        if self.cny_data is None or self.cny_data.data.empty:
            return None

        start_time = current_time - time_range
        tz = self.cny_data.data.index.tz
        if tz is not None:
             if start_time.tzinfo is None:
                 start_time = start_time.replace(tzinfo=tz)
             if current_time.tzinfo is None:
                 current_time = current_time.replace(tzinfo=tz)

        return self.cny_data.data.loc[start_time:current_time]