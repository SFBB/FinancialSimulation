from enum import Enum
import datetime
from abc import ABC, abstractmethod
from stock_util import stock_info
from math_util import math_util
import csv



def extract_close_price(stock_info: stock_info, date_time: datetime.datetime):
    if len(stock_info.get_today_price(date_time).close.values) > 0:
        return stock_info.get_today_price(date_time).close.values[0]
    return None

class buy_or_sell_choice(Enum):
    Buy = 0, "Buy"
    Sell = 1, "Sell"
    DoNothing = 2, "DoNothing"
    
    def __new__(cls, value, name):
        member = object.__new__(cls)
        member._value_ = value
        member.fullname = name
        return member

    def __int__(self):
        return self.value



class investment_record(ABC):
    def __init__(self):
        self.records = []

    def handle_choice(self, date_time: datetime.datetime, stock_info: stock_info, choice: buy_or_sell_choice, number: float, total_money: float, total_number: float) -> tuple[float, float]:
        if choice == buy_or_sell_choice.DoNothing:
            return 0, 0
        price = extract_close_price(stock_info, date_time)
        if price is None:
            return 0, 0
        asset_value = price * number
        delta_asset_value = asset_value
        delta_number = number
        if choice == buy_or_sell_choice.Buy:
            if total_money == 0:
                return 0, 0
            if asset_value > total_money:
                asset_value = total_money
                number = asset_value / price
            delta_asset_value = -asset_value
            delta_number = number
        elif choice == buy_or_sell_choice.Sell:
            if total_number == 0:
                return 0
            if number > total_number:
                number = total_number
                asset_value = price * number
            delta_asset_value = asset_value
            delta_number = -number
        self.records.append({
            "time": date_time,
            "price": price,
            "stock_info": stock_info,
            "choice": choice,
            "number": number,
            "money_value": asset_value,
            "delta_money_value": delta_asset_value,
            "delta_number": delta_number
        })
        
        return delta_asset_value, delta_number

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

        self.initial_money = 0
        self.changed_money = 0

        self.hold_stock_number = {}

        self.initialized = False

    def get_stock_names(self):
        return self.stock_names

    def tick(self, latest_stocks_info: dict[str, stock_info], current_time: datetime.datetime):
        if not self.initialized:
            for ticket in self.stock_names:
                self.hold_stock_number[ticket] = 0
            self.initialized = True

        self.latest_stocks_info = latest_stocks_info
        self.today_time = current_time
        # we allow strategy to re-think every tick.
        self.handle_choice(self.make_choice())

    def handle_choice(self, choice):
        for ticket in choice.keys():
            changed_value, changed_number = self.__investments_info__.handle_choice(
                self.today_time,
                self.latest_stocks_info[ticket],
                choice[ticket][0],
                choice[ticket][1],
                self.initial_money + self.changed_money,
                self.hold_stock_number[ticket]
            )
            self.changed_money += changed_value
            if choice[ticket][0] != buy_or_sell_choice.DoNothing:
                if ticket not in self.hold_stock_number.keys():
                    self.hold_stock_number[ticket] = 0
                self.hold_stock_number[ticket] += changed_number

    @abstractmethod
    def end(self):
        pass

    @abstractmethod
    def make_choice(self) -> dict[str, tuple[buy_or_sell_choice, float]]:
        return {}

class MyStrategy(strategy_base):
    def __init__(self):
        super(MyStrategy, self).__init__()
        self.stock_names = ["GOOGL"]
        self.initial_money = 1000000

        self.has_bet = False
        self.bet_price = 0
        self.bet_target_price = 0
        self.bet_date = datetime.datetime.now()

    def make_choice(self) -> dict[str, tuple[buy_or_sell_choice, float]]:
        today_price = extract_close_price(self.latest_stocks_info["GOOGL"], self.today_time)
        GOOGL_history_price = self.latest_stocks_info["GOOGL"].get_history_price(self.today_time)
        x = GOOGL_history_price.loc[GOOGL_history_price.index.get_level_values("date") > (self.today_time - datetime.timedelta(days=30)).date()].close.values
        if len(x) < 2:
            return {}
        hurst_exponent, c = math_util.rs_analysis(x, 2)
        if hurst_exponent > 0.6:
            trending_rate = (list(x)[-1] - list(x)[0]) / list(x)[0]
            if trending_rate > 0 and not self.has_bet:
                # self.has_bet = True
                self.bet_price = x[-1]
                self.bet_target_price = x[-1] * trending_rate
                self.bet_date = self.today_time
                return {"GOOGL": (buy_or_sell_choice.Buy, (self.initial_money + self.changed_money) / x[-1])}
        if today_price is not None and self.today_time - self.bet_date > datetime.timedelta(days=60) and self.bet_target_price < today_price:
            return {"GOOGL": (buy_or_sell_choice.Sell, 100)}
        return {}

    def end(self):
        GOOGL_history_price = self.latest_stocks_info["GOOGL"].get_history_price(self.today_time)
        x = GOOGL_history_price.loc[GOOGL_history_price.index.get_level_values("date") > (self.today_time - datetime.timedelta(days=30)).date()].close.values
        records = self.__investments_info__.get_records()
        with open("records.csv", "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["time", "price", "choice", "money_value", "number", "delta_money_value", "delta_number"])
            for record in records:
                writer.writerow([record["time"], record["price"], int(record["choice"]), record["asset_value"], record["number"], record["delta_asset_value"], record["delta_number"]])
        print("Money change: {}, asset value change: {}".format(self.changed_money, self.changed_money + self.hold_stock_number["GOOGL"] * x[-1]))



if __name__ == "__main__":
    MyStrategy_1 = MyStrategy()
    # print(MyStrategy_1.tick({"GOOGL": stock_info("GOOGL")}))
