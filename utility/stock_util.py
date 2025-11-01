from yahooquery import Ticker
import pandas as pd
import datetime
from enum import Enum
from abc import ABC, abstractmethod
import os



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

class stock_info():
    def __init__(self, ticket_name, start_time: datetime.datetime, end_time: datetime.datetime, interval: datetime.timedelta):
        self.ticket_name = ticket_name
        self.start_time = start_time
        self.end_time = end_time
        self.interval = interval
        self.stock = stock(ticket_name)
        self.history_price_data = pd.DataFrame()

    def __get_cache_path(self) -> str:
        return "cache/{}_{}_{}_{}.pkl".format(self.ticket_name, self.start_time.strftime("%Y-%m-%d"), self.end_time.strftime("%Y-%m-%d"), self.interval.days)

    def __has_cache(self):
        return os.path.exists(self.__get_cache_path())

    def __load_cache(self):
        self.history_price_data = pd.read_pickle(self.__get_cache_path())

    def __update_cache(self):
        if not os.path.exists("cache"):
            os.makedirs("cache")
        self.history_price_data.to_pickle(self.__get_cache_path())

    def initialize(self):
        if self.__has_cache():
            try:
                self.__load_cache()
            except Exception as e:
                print(e)
                self.update()
        else:
            self.update()

    # update stock info
    def update(self):
        interval = "1d"
        if self.interval.days > 0:
            interval = "{}d".format(self.interval.days)
        elif self.interval.seconds > 0:
            interval = "{}h".format(self.interval.seconds // 60 // 60)
        self.history_price_data = self.stock.history("100y", interval, None, self.end_time)
        self.__update_cache()

    def get_today_price(self, current_time: datetime.datetime) -> pd.DataFrame:
        return self.history_price_data.loc[self.history_price_data.index.get_level_values("date") == current_time.date()]

    def get_history_price(self, current_time: datetime.datetime):
        return self.history_price_data.loc[self.history_price_data.index.get_level_values("date") <= current_time.date()]

def extract_close_price(stock_info: stock_info, date_time: datetime.datetime):
    if len(stock_info.get_today_price(date_time).close.values) > 0:
        return stock_info.get_today_price(date_time).close.values[0]
    return None

class promise_base(ABC):
    def __init__(self, promise_price: float, promise_datetime: datetime.datetime, stock: stock_info, ticket_name: str, number: float):
        self.promise_price = promise_price
        self.promise_datetime = promise_datetime
        self.stock = stock
        self.ticket_name = ticket_name
        self.number = number

    @abstractmethod
    def do_promise_or_not(self, current_datetime: datetime.datetime) -> tuple[bool, buy_or_sell_choice]:
        return False, buy_or_sell_choice.DoNothing

class promise_buy(promise_base):
    def __init__(self, promise_price: float, promise_datetime: datetime.datetime, stock: stock_info, ticket_name: str, number: float):
        super(promise_buy, self).__init__(promise_price, promise_datetime, stock, ticket_name, number)
    
    def do_promise_or_not(self, current_datetime: datetime.datetime) -> tuple[bool, buy_or_sell_choice]:
        if current_datetime > self.promise_datetime:
            return True, buy_or_sell_choice.Buy
        today_price = extract_close_price(self.stock, current_datetime)
        if today_price == None:
            return False, buy_or_sell_choice.DoNothing
        elif today_price <= self.promise_price:
            return True, buy_or_sell_choice.Buy
        return False, buy_or_sell_choice.DoNothing

class promise_sell(promise_base):
    def __init__(self, promise_price: float, promise_datetime: datetime.datetime, stock: stock_info, ticket_name: str, number: float):
        super(promise_sell, self).__init__(promise_price, promise_datetime, stock, ticket_name, number)
    
    def do_promise_or_not(self, current_datetime: datetime.datetime) -> tuple[bool, buy_or_sell_choice]:
        if current_datetime > self.promise_datetime:
            return True, buy_or_sell_choice.Sell
        today_price = extract_close_price(self.stock, current_datetime)
        if today_price == None:
            return False, buy_or_sell_choice.DoNothing
        elif today_price >= self.promise_price:
            return True, buy_or_sell_choice.Sell
        return False, buy_or_sell_choice.DoNothing



if __name__ == "__main__":
    si = stock_info("GOOGL", datetime.datetime(2012, 12, 12), datetime.datetime.now(), datetime.timedelta(days=1))
    si.initialize()
    print(si.get_today_price(datetime.datetime.now()))
