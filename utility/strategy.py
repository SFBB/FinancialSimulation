import datetime
from abc import ABC, abstractmethod
from stock_util import stock_info, buy_or_sell_choice, promise_buy, promise_sell, extract_close_price
from economic_util import economic_info_base
from math_util import math_util
import csv
import numpy as np



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
            if asset_value > total_money:
                asset_value = total_money
                number = asset_value / price
            delta_asset_value = -asset_value
            delta_number = number
        elif choice == buy_or_sell_choice.Sell:
            if number > total_number:
                number = total_number
                asset_value = price * number
            delta_asset_value = asset_value
            delta_number = -number
        if number == 0:
            return 0, 0
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
        self.latest_economics_info = {}
        self.today_time = datetime.datetime.now()

        self.initial_money = 0
        self.changed_money = 0

        self.hold_stock_number = {}

        self.promises = [] # list[promise_base]

        self.initialized = False

    def get_stock_names(self):
        return self.stock_names

    def tick(self, latest_stocks_info: dict[str, stock_info], latest_economics_info: dict[str, economic_info_base], current_time: datetime.datetime):
        if not self.initialized:
            for ticket in self.stock_names:
                self.hold_stock_number[ticket] = 0
            self.initialized = True

        self.latest_stocks_info = latest_stocks_info
        self.latest_economics_info = latest_economics_info
        self.today_time = current_time
        # we allow strategy to re-think every tick.
        choice_list = self.make_choice()
        choice_list += self.handle_promises()
        for choice in choice_list:
            self.handle_choice(choice)

    def handle_promises(self):
        choice_list = []
        promised_list = []
        for promise in self.promises:
            do_it, choice = promise.do_promise_or_not(self.today_time)
            if do_it:
                promised_list.append(promise)
                choice_list.append({promise.ticket_name: (choice, promise.number)})
        for promised in promised_list:
            self.promises.remove(promised)
        return choice_list

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

    def new_promise(self, promise):
        self.promises.append(promise)

    @abstractmethod
    def end(self):
        pass

    @abstractmethod
    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
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
        self.promises = [] # list[promise_base]

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        today_price = extract_close_price(self.latest_stocks_info["GOOGL"], self.today_time)
        if today_price == None:
            return []
        choices = []
        GOOGL_history_price = self.latest_stocks_info["GOOGL"].get_history_price(self.today_time)
        x = GOOGL_history_price.loc[GOOGL_history_price.index.get_level_values("date") > (self.today_time - datetime.timedelta(days=30)).date()].close.values
        if len(x) < 2:
            return choices
        hurst_exponent, c = math_util.rs_analysis(x, 2)
        mean = np.average(list(x))
        if hurst_exponent > 0.6:
            trending_rate = (list(x)[-1] - list(x)[0]) / list(x)[0]
            if trending_rate > 0 and not self.has_bet:
                # self.has_bet = True
                self.bet_price = x[-1]
                self.bet_target_price = x[-1] * trending_rate
                self.bet_date = self.today_time
                choices.append({"GOOGL": (buy_or_sell_choice.Buy, (100 + self.hold_stock_number["GOOGL"] * 2))})
                if self.initial_money + self.changed_money > 0:
                    self.new_promise(promise_sell(mean * 1.1, self.today_time + datetime.timedelta(days=60), self.latest_stocks_info["GOOGL"], "GOOGL", 100 + self.hold_stock_number["GOOGL"] * 2))
                # choice = {"GOOGL": (buy_or_sell_choice.Buy, (self.initial_money + self.changed_money) / x[-1])}
        elif hurst_exponent < 0.4:
            if today_price < mean * 0.9:
                choices.append({"GOOGL": (buy_or_sell_choice.Buy, 1000)})
                self.new_promise(promise_sell(mean, self.today_time + datetime.timedelta(days=30), self.latest_stocks_info["GOOGL"], "GOOGL", 1000))
            else:
                self.new_promise(promise_buy(mean * 0.9, self.today_time + datetime.timedelta(days = 30), self.latest_stocks_info["GOOGL"], "GOOGL", 1000))
        return choices

    def end(self):
        GOOGL_history_price = self.latest_stocks_info["GOOGL"].get_history_price(self.today_time)
        x = GOOGL_history_price.loc[GOOGL_history_price.index.get_level_values("date") > (self.today_time - datetime.timedelta(days=30)).date()].close.values
        records = self.__investments_info__.get_records()
        with open("records.csv", "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["time", "price", "choice", "money_value", "number", "delta_money_value", "delta_number"])
            for record in records:
                writer.writerow([record["time"], record["price"], int(record["choice"]), record["money_value"], record["number"], record["delta_money_value"], record["delta_number"]])
        print("Money change: {}, asset value change: {}".format(self.changed_money, self.changed_money + self.hold_stock_number["GOOGL"] * x[-1]))



if __name__ == "__main__":
    MyStrategy_1 = MyStrategy()
    # print(MyStrategy_1.tick({"GOOGL": stock_info("GOOGL")}))
