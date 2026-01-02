class AAPLStrategy(strategy_base):
    """
    Strategy for AAPL using Scientific Hurst Exponent.
    - Filter: Scientific Hurst > 0.55 (Weak Trend or stronger).
    - Entry: Trending Rate (Price Slope) > Threshold using log returns.
    - Exit: Stop Loss / Take Profit / Promise.
    """
    def __init__(
        self,
        initial_money=1000000,
        hurst_threshold=0.55,
        trending_rate_threshold=0.001, # Adjusted for daily log return scale if used, or stick to simple rate
        stop_loss_pct=0.03,
        take_profit_pct=0.10,
    ):
        super(AAPLStrategy, self).__init__()
        self.stock_names = ["AAPL"]
        self.initial_money = initial_money
        self.hurst_threshold = hurst_threshold
        self.trending_rate_threshold = trending_rate_threshold
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        
        self.has_bet = False
        self.bet_price = 0
        self.bet_date = None

    def get_name(self):
        return f"AAPLStrategy(H_thresh={self.hurst_threshold}, Trend={self.trending_rate_threshold})"

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        today_price = extract_close_price(
            self.latest_stocks_info["AAPL"], self.today_time
        )
        if today_price is None or np.isnan(today_price):
            return choices

        # Risk Management
        if self.has_bet:
            sell_signal = False
            # Stop Loss
            if today_price < self.bet_price * (1 - self.stop_loss_pct):
                sell_signal = True
            # Take Profit
            elif today_price > self.bet_price * (1 + self.take_profit_pct):
                sell_signal = True
            # Time exit (e.g. 30 days) - Optional, similar to Promise logic
            elif (self.today_time - self.bet_date).days > 30:
                 # Check if we are profitable or flat? 
                 pass

            if sell_signal:
                choices.append(
                    {
                        "AAPL": (
                            buy_or_sell_choice.Sell,
                            self.hold_stock_number.get("AAPL", 0),
                        )
                    }
                )
                self.has_bet = False
                return choices

        # Entry Logic
        history = self.latest_stocks_info["AAPL"].get_history_price(self.today_time)
        x = history["close"].values
        if len(x) < 50:
            return choices

        # 1. Scientific Hurst Filter
        # Calculate on last 200 days? 
        window = 200
        if len(x) > window:
            analysis_window = x[-window:]
        else:
            analysis_window = x
            
        H, _ = math_util.rs_analysis_scientific(analysis_window)
        
        if H > self.hurst_threshold:
            # Trend Persisting
            # 2. Momentum Check
            # Use simple return over last 20 days
            momentum = (x[-1] - x[-20]) / x[-20]
            
            if momentum > self.trending_rate_threshold and not self.has_bet:
                amount = self.initial_money + self.changed_money
                number = (amount * 0.5) / today_price # Invest 50%
                
                choices.append({"AAPL": (buy_or_sell_choice.Buy, number)})
                self.has_bet = True
                self.bet_price = today_price
                self.bet_date = self.today_time
        
        return choices
