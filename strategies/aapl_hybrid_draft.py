class AAPLHybridStrategy(strategy_base):
    """
    Hybrid FMH/EMH Strategy for AAPL.

    Concept:
    - Efficient Market (EMH): When Hurst is near 0.5 (Random Walk), we assume prices are efficient.
      Best strategy is to passively capture the market drift (Beta). We hold a baseline 50% allocation.
    - Fractal Market (FMH):
      - Trending (H > 0.6): Market has memory/persistence. We increase allocation to 100% to capture Alpha.
      - Mean Reversion (H < 0.4): Market is anti-persistent. We buy dips (increase to 100%).

    Allocation Logic:
    - Neutral (EMH): 50% Exposure
    - Edge (FMH): 100% Exposure
    - Risk Off: 0% Exposure (Stop Loss or Extreme Volatility)
    """

    def __init__(
        self,
        base_allocation=0.5,
        max_allocation=1.0,
        stop_loss_pct=0.07,
    ):
        super(AAPLHybridStrategy, self).__init__()
        self.stock_names = ["AAPL"]
        self.base_allocation = base_allocation
        self.max_allocation = max_allocation
        self.stop_loss_pct = stop_loss_pct

        self.entry_price = 0
        self.max_price = 0

    def get_name(self):
        return "AAPLHybridStrategy(FMH+EMH)"

    def get_stock_source(self, stock_name):
        return "yahoo"

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        today_price = extract_close_price(
            self.latest_stocks_info["AAPL"], self.today_time
        )
        if today_price is None or np.isnan(today_price):
            return choices

        # 1. Update Portfolio State
        shares = self.hold_stock_number.get("AAPL", 0)
        cash = self.initial_money + self.changed_money
        equity = cash + (shares * today_price)
        current_alloc = (shares * today_price) / equity if equity > 0 else 0

        # Track High Watermark for Trailing Stop
        if shares > 0:
            self.max_price = max(self.max_price, today_price)
        else:
            self.max_price = today_price
            self.entry_price = today_price

        # 2. Risk Management (Trailing Stop)
        # If drawdown > stop_loss, exit everything and cooldown?
        # For this hybrid, let's reset to 0% if stop hit, then need re-entry signal.
        if shares > 0 and today_price < self.max_price * (1 - self.stop_loss_pct):
            # STOP LOSS TRIGGERED
            # Sell all
            choices.append({"AAPL": (buy_or_sell_choice.Sell, shares)})
            self.max_price = 0  # Reset
            # We enforce a cooldown or just wait for next signal?
            # For simplicity, we just exit this tick. Next tick might re-enter if signal persists,
            # but usually price drop implies momentum lost, so signal might change.
            return choices

        # 3. Calculate Hurst (Scientific)
        history = self.latest_stocks_info["AAPL"].get_history_price(self.today_time)
        x = history["close"].values
        # Need window
        if len(x) < 200:
            return choices

        window = 200  # Lookback for regime detection
        analysis_window = x[-window:] if len(x) > window else x
        H, _ = math_util.rs_analysis_scientific(analysis_window)

        # 4. Determine Target Allocation
        target_alloc = 0.0

        # Regime Classification
        if 0.45 <= H <= 0.55:
            # EMH Regime (Random Walk) -> Base Allocation (Capture Drift)
            target_alloc = self.base_allocation
        elif H > 0.55:
            # FMH Trend Regime -> Max Allocation (Capture Trend)
            # Only if momentum agrees?
            momentum = (x[-1] - x[-20]) / x[-20]
            if momentum > 0:
                target_alloc = self.max_allocation
            else:
                # Trend exists (H high) but Price is falling?
                # This implies "Persistently Down". Short or Cash.
                target_alloc = 0.0
        elif H < 0.45:
            # FMH Mean Reversion -> Buy Dips
            # If price < MA_50, buy
            ma_50 = np.mean(x[-50:])
            if today_price < ma_50:
                target_alloc = self.max_allocation
            else:
                # Price high in mean reversion -> Sell/Hold Base
                target_alloc = self.base_allocation

        # 5. Rebalance
        desired_value = equity * target_alloc
        current_value = shares * today_price
        diff_value = desired_value - current_value

        # Threshold to avoid tiny trades (e.g. 1% drift)
        if abs(diff_value) < equity * 0.02:
            return choices

        if diff_value > 0:
            num_to_buy = diff_value / today_price
            choices.append({"AAPL": (buy_or_sell_choice.Buy, num_to_buy)})
        elif diff_value < 0:
            num_to_sell = abs(diff_value) / today_price
            choices.append({"AAPL": (buy_or_sell_choice.Sell, num_to_sell)})

        return choices
