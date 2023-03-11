from enum import Enum
import datetime
from abc import ABC, abstractmethod
from stock_util import stock_info



def extract_close_price(stock_info: stock_info, date_time: datetime.datetime):
    if len(stock_info.get_today_price(date_time).close.values) > 0:
        return stock_info.get_today_price(date_time).close.values[0]
    return None

class buy_or_sell_choice(Enum):
    Buy = 0
    Sell = 1
    DoNothing = 2

class investment_record(ABC):
    def __init__(self):
        self.records = []

    def handle_choice(self, date_time: datetime.datetime, stock_info: stock_info, choice: buy_or_sell_choice, number: float):
        price = extract_close_price(stock_info, date_time)
        if price is None:
            return
        self.records.append({
            "time": date_time,
            "price": price,
            "stock_info": stock_info,
            "choice": choice,
            "number": number,
            "asset_value": price * number
        })

    def get_records(self):
        return self.records.copy()

    def get_statistics(self):
        pass

class strategy_base(ABC):
    def __init__(self):
        self.__investments_info__ = investment_record()
        self.stock_names = [] # list[str]
        self.latest_stocks_info = {}
        self.today_time = datetime.datetime.now()

    def get_stock_names(self):
        return self.stock_names

    def tick(self, latest_stocks_info: dict[str, stock_info], current_time: datetime.datetime):
        self.latest_stocks_info = latest_stocks_info
        self.today_time = current_time
        # we allow strategy to re-think every tick.
        self.handle_choice(self.make_choice())

    def handle_choice(self, choice):
        for ticket in choice.keys():
            self.__investments_info__.handle_choice(
                self.today_time,
                self.latest_stocks_info[ticket],
                choice[ticket][0],
                choice[ticket][1]
            )

    @abstractmethod
    def make_choice(self) -> dict[str, tuple[buy_or_sell_choice, float]]:
        return {}

    # Used to record our investment history.
    @abstractmethod
    def log(self):
        pass

    # save logs
    @abstractmethod
    def save(self):
        pass

class MyStrategy(strategy_base):
    def __init__(self):
        super(MyStrategy, self).__init__()
        self.stock_names = ["GOOGL"]
        pass

    def make_choice(self) -> dict[str, tuple[buy_or_sell_choice, float]]:
        today_price = extract_close_price(self.latest_stocks_info["GOOGL"], self.today_time)
        if today_price is not None and today_price > 10:
            return {"GOOGL": (buy_or_sell_choice.Buy, 100)}
        return super().make_choice()

    def log(self):
        pass

    def save(self):
        pass



if __name__ == "__main__":
    MyStrategy_1 = MyStrategy()
    # print(MyStrategy_1.tick({"GOOGL": stock_info("GOOGL")}))
