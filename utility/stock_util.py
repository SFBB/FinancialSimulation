from yahooquery import Ticker
import matplotlib.pyplot as plt



class stock(Ticker):
    def __init__(self, symbols, **kwargs):
        super(stock, self).__init__(symbols, **kwargs)
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
