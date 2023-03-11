from enum import Enum
import datetime
from abc import ABC, abstractmethod
from stock_util import stock_info



class buy_or_sell_choice(Enum):
    Buy = 0
    Sell = 1
    DoNothing = 2

class investment_record(ABC):
    def __init__(self):
        self.records = []

    def handle_choice(self, date_time: datetime.datetime, stock_info: stock_info, choice: buy_or_sell_choice, number: float):
        price = stock_info.get_today_price(date_time).loc[date_time.date()].close
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
        choice = self.make_choice()

    @abstractmethod
    def make_choice(self) -> dict[str, tuple[buy_or_sell_choice, float]]:
        return {"None": (buy_or_sell_choice.DoNothing, 0)},

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
        print(self.today_time)
        return super().make_choice()

    def log(self):
        pass

    def save(self):
        pass



if __name__ == "__main__":
    MyStrategy_1 = MyStrategy()
    # print(MyStrategy_1.tick({"GOOGL": stock_info("GOOGL")}))
