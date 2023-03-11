from enum import Enum
import datetime
from abc import ABC, abstractmethod
from stock_util import stock_info



class buy_or_sell_choice(Enum):
    Buy = 0
    Sell = 1
    DoNothing = 2

class investment_info(ABC):
    def __init__(self):
        pass

    def update(self, stock_info: stock_info):
        pass

class strategy_base(ABC):
    def __init__(self):
        self.__investments_info = {} # dict[str, investment_info]
        self.__stock_names = [] # list[str]

    def get_stock_names(self):
        return self.__stock_names

    def tick(self, stocks_info: dict[str, stock_info], current_time: datetime.datetime):
        for stock_name in self.__stock_names:
            if stock_name not in stocks_info.keys():
                # there is no such stock info in our simulation
                continue
            if stock_name not in self.__investments_info.keys():
                # if we didn't have such stock name in our investments info, we add it.
                self.__investments_info[stock_name] = investment_info()
            self.__investments_info[stock_name].update(stocks_info[stock_name])

    def set_investment_info(self, customized_investment_info: investment_info):
        self.investment_info = customized_investment_info

    @abstractmethod
    def make_choice(self) -> dict[str, buy_or_sell_choice]:
        return {"None": buy_or_sell_choice.DoNothing}

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

    def make_choice(self) -> dict[str, buy_or_sell_choice]:
        return super().make_choice()

    def log(self):
        pass

    def save(self):
        pass

if __name__ == "__main__":
    MyStrategy_1 = MyStrategy()
    # print(MyStrategy_1.tick({"GOOGL": stock_info("GOOGL")}))
