from utility.strategy import *



class GOOGLStrategy(strategy_base):
    def __init__(self):
        super(GOOGLStrategy, self).__init__()
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
        x = GOOGL_history_price.loc[GOOGL_history_price.index.get_level_values("date") > (self.today_time - datetime.timedelta(days=90)).date()].close.values
        if len(x) < 2:
            return choices
        hurst_exponent, c = math_util.rs_analysis(x, 2)
        mean = np.average(list(x))
        if hurst_exponent > 0.9 and hurst_exponent < 0.95:
            trending_rate = (list(x)[-1] - list(x)[0]) / list(x)[0]
            if trending_rate > 0.1 and not self.has_bet:
                # print(trending_rate, self.today_time)
                # self.has_bet = True
                self.bet_price = x[-1]
                self.bet_target_price = x[-1] * trending_rate
                self.bet_date = self.today_time
                number = np.clip(10000 - self.hold_stock_number["GOOGL"] * 0.5, 0, 10000)
                choices.append({"GOOGL": (buy_or_sell_choice.Buy, number)})
                if self.initial_money + self.changed_money > 0:
                    self.new_promise(promise_sell(mean * 1.1, self.today_time + datetime.timedelta(days=16), self.latest_stocks_info["GOOGL"], "GOOGL", number))
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
