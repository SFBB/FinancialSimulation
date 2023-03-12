from strategy import strategy_base, MyStrategy
from abc import ABC, abstractmethod
from stock_util import stock_info
from economic_util import economic_info_base
import datetime



class simulation_kernel():
    def __init__(self, start_time: datetime.datetime, end_time: datetime.datetime, interval: datetime.timedelta):
        self.__strategies__ = [] # list[strategy_base]
        self.__stocks_info__ = {} # dict[str, stock_info]
        self.__economics_info__ = {} # dict[str, stock_info]


        self.__start_time__ = start_time
        self.__end_time__ = end_time
        self.__current_time__ = self.__start_time__
        self.__interval__ = interval

    def add_strategy(self, strategy: strategy_base):
        self.__strategies__.append(strategy)
        self.initialize()

    def add_economic_info(self, name: str, economic_info: economic_info_base):
        self.__economics_info__[name] = economic_info

    def initialize(self):
        self.__collect_strategies_stock_names__()

    def __collect_strategies_stock_names__(self):
        for strategy in self.__strategies__:
            stock_names = strategy.get_stock_names()
            for stock_name in stock_names:
                self.__stocks_info__[stock_name] = stock_info(stock_name, self.__start_time__, self.__end_time__, self.__interval__)
                self.__stocks_info__[stock_name].update() # retrive data from web.

    def update_stock(self):
        pass

    def update_economic(self):
        for economic_name in self.__economics_info__.keys():
            self.__economics_info__[economic_name].update()

    def run(self):
        while self.__current_time__ <= self.__end_time__:
            self.update_stock()
            self.update_economic()
            for strategy in self.__strategies__:
                stock_infos = {}
                for stock_name in strategy.get_stock_names():
                    stock_infos[stock_name] = self.__stocks_info__[stock_name]
                strategy.tick(stock_infos, self.__economics_info__, self.__current_time__)
            
            self.__current_time__ += self.__interval__

    def end(self):
        for strategy in self.__strategies__:
            strategy.end()



if __name__ == "__main__":
    sk = simulation_kernel(datetime.datetime(2012, 12, 12), datetime.datetime.now(), datetime.timedelta(days=1))
    sk.add_strategy(MyStrategy())
    sk.initialize()
    sk.run()
    sk.end()
