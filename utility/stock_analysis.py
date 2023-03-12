from yahooquery import Ticker
from pandas import DataFrame as df
import matplotlib.pyplot as plt
from enum import Enum



class Stock_Judgement(Enum):
    Trending = 0
    Random = 1
    Revert_Mean = 2

class Stock(Ticker):
    def __init__(self, symbols, **kwargs):
        super(Stock, self).__init__(symbols, **kwargs)
        self.symbols = symbols

    def get_hurst_exponent(self):
        pass

    def current_judgement(self):
        pass

    def disp(self,
        column: str,
        period="ytd",
        interval="1d",
        start=None,
        end=None,
        adj_timezone=True,
        adj_ohlc=False,
    ):
        self.history(period, interval, start, end, adj_timezone, adj_ohlc).plot(y=column, kind="line")
        plt.title("Stock {}".format(str(self.symbols)))
        plt.show()

class Simulation():
    def __init__(self):
        pass

    def do_simulation(self):
        pass

    def __log(self):
        pass



if __name__ == "__main__":
    stock = Stock('GOOGL')
    history = stock.history("5y", "1d")

    print(stock.current_judgement())

    stock.disp("close", "3y", "1d")
