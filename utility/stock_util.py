from yahooquery import Ticker
import pandas as pd
import datetime



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

    def update(self):
        interval = "1d"
        if self.interval.days > 0:
            interval = "{}d".format(self.interval.days)
        elif self.interval.seconds > 0:
            interval = "{}m".format(self.interval.seconds // 60)
        self.history_price_data = self.stock.history("100y", interval, None, self.end_time)

    def get_today_price(self, current_time: datetime.datetime) -> pd.DataFrame:
        return self.history_price_data.loc[self.history_price_data.index.get_level_values("date") == current_time.date()]

    def get_history_price(self, current_time: datetime.datetime):
        return self.history_price_data.loc[self.history_price_data.index.get_level_values("date") <= current_time.date()]



if __name__ == "__main__":
    si = stock_info("GOOGL", datetime.datetime(2012, 12, 12), datetime.datetime.now(), datetime.timedelta(days=1))
    si.update()
    print(si.get_today_price(datetime.datetime.now()))
