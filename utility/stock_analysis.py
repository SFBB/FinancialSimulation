from yahooquery import Ticker
from pandas import DataFrame as df
import matplotlib.pyplot as plt
from enum import Enum


def get_moving_average(data, window):
    return data.rolling(window=window).mean()


def get_macd(data, fast=12, slow=26, signal=9):
    """
    Calculate MACD, Signal Line, and Histogram.
    Returns tuple: (macd_line, signal_line, histogram)
    """
    exp1 = data.ewm(span=fast, adjust=False).mean()
    exp2 = data.ewm(span=slow, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def get_rsi(data, window=14):
    """
    Calculate Relative Strength Index (RSI).
    """
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi



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
