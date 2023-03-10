from strategy import strategy_base, buy_or_sell_choice, MyStrategy
from abc import ABC, abstractmethod
from stock_util import stock



class simulation_kernel():
    def __init__(self):
        self.__strategies__ = [] # list[strategy_base]
        self.__stocks_info__ = {} # dict[str, stock]

    def add_strategy(self, strategy: strategy_base):
        self.__strategies__.append(strategy)

    def initialize(self):
        self.__collect_strategies_stock_names()

    def __collect_strategies_stock_names(self):
        for strategy in self.__strategies__:
            stock_names = strategy.get_stock_names()
            for stock_name in stock_names:
                self.__stocks_info__[stock_name] = stock(stock_name)

    def update_stock(self):
        pass

    def run(self):
        while True:
            for strategy in self.__strategies__:
                strategy.tick(self.__stocks_info__)

if __name__ == "__main__":
    sk = simulation_kernel()
    sk.add_strategy(MyStrategy())
    sk.initialize()
