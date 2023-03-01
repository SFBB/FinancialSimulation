from enum import Enum
import datetime
from abc import ABC, abstractmethod
from stock_util import stock



class buy_or_sell_choice(Enum):
    Buy = 0
    Sell = 1
    DoNothing = 2

class investment_info(ABC):
    def __init__(self):
        pass

    def update(self, stock_info: stock):
        pass

class strategy_base(ABC):
    def __init__(self):
        self.current = datetime.datetime.now()
        self.start = datetime.datetime.now()
        self.end = datetime.datetime.now()
        self.interval = datetime.timedelta()
        self.investment_info = investment_info()

    def tick(self, stock_info: stock):
        self.investment_info.update(stock_info)

    def set_investment_info(self, customized_investment_info: investment_info):
        self.investment_info = customized_investment_info

    @abstractmethod
    def make_choice(self) -> buy_or_sell_choice:
        return buy_or_sell_choice.DoNothing

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
        pass

    def make_choice(self) -> buy_or_sell_choice:
        return super().make_choice()

    def log(self):
        pass

    def save(self):
        pass

if __name__ == "__main__":
    MyStrategy_1 = MyStrategy()
    print(MyStrategy_1.tick(stock()))
    MyStrategy_1.investment_info.update(stock())
