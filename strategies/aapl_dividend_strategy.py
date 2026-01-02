from utility.strategy import strategy_base, buy_or_sell_choice
from utility.stock_util import extract_close_price
import numpy as np
import pandas as pd
import datetime

class AAPL_Dividend_Strategy(strategy_base):
    """
    AAPL Dividend Yield Strategy
    ----------------------------
    Uses Dividend Yield as a valuation metric for AAPL.
    While AAPL is a growth stock, its yield spikes during major corrections (Value Zone).
    
    Parameters:
    - Buy Yield > 0.6% (Approx Price $160 for $1.00 Div) -> Value Zone.
    - Sell Yield < 0.3% (Approx Price $330 for $1.00 Div) -> Bubble Zone.
    """

    def __init__(
        self,
        ticker="AAPL",
        initial_money=1000000,
        buy_yield=0.006,  # 0.6%
        sell_yield=0.003, # 0.3%
        trend_ma=100,
        stop_loss_pct=0.10
    ):
        super().__init__()
        self.stock_names = [ticker]
        self.ticker = ticker
        self.initial_money = initial_money
        
        self.buy_yield = buy_yield
        self.sell_yield = sell_yield
        self.trend_ma = trend_ma
        self.stop_loss_pct = stop_loss_pct
        
        self.max_price = 0

    def get_name(self):
        return f"AAPL_DivYield(Buy{self.buy_yield*100:.1f}%_Sell{self.sell_yield*100:.1f}%)"

    def get_stock_source(self, stock_name):
        return "yahoo"

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        stock_data = self.latest_stocks_info[self.ticker]
        today_price = extract_close_price(stock_data, self.today_time)
        
        if today_price is None or np.isnan(today_price): return choices

        shares = self.hold_stock_number.get(self.ticker, 0)
        cash = self.initial_money + self.changed_money
        total_equity = cash + (shares * today_price)
        if total_equity <= 0: return choices

        hist = stock_data.get_history_price(self.today_time)
        # Need 1 year of history for TTM Yield
        if len(hist) < 300: return choices
        
        # --- Calc Yield ---
        current_yield = 0.0
        if 'dividends' in hist.columns:
            one_year_ago = self.today_time - datetime.timedelta(days=365)
            mask = hist.index >= pd.Timestamp(one_year_ago.date())
            ttm_divs = hist.loc[mask, 'dividends'].sum()
            
            if ttm_divs > 0:
                current_yield = ttm_divs / today_price
        
        # --- Indicators ---
        ema_trend = hist['close'].ewm(span=self.trend_ma, adjust=False).mean().iloc[-1]
        is_uptrend = today_price > ema_trend
        
        # Debug Log (Jan 1st)
        if self.today_time.day == 1 and self.today_time.month == 1:
             print(f"Date: {self.today_time.date()} | Price: {today_price:.2f} | Divs(TTM): {ttm_divs:.2f} | Yield: {current_yield*100:.2f}%")

        action = "HOLD"
        
        # === SELL ===
        if shares > 0:
            self.max_price = max(self.max_price, today_price)
            # Stop Loss
            if today_price < self.max_price * (1 - self.stop_loss_pct):
                action = "SELL"
            # Overvaluation (Low Yield)
            elif current_yield < self.sell_yield and current_yield > 0:
                action = "SELL"
        
        # === BUY ===
        if action != "SELL":
            # Undervalued (High Yield) + Trend
            if current_yield > self.buy_yield and is_uptrend:
                action = "BUY"
                
        # === EXECUTE ===
        if action == "SELL" and shares > 0:
            choices.append({self.ticker: (buy_or_sell_choice.Sell, shares)})
            self.max_price = 0
            
        elif action == "BUY":
            target_val = total_equity * 1.0 # Full allocation
            current_val = shares * today_price
            diff = target_val - current_val
            
            if diff > total_equity * 0.1:
                num = diff / today_price
                choices.append({self.ticker: (buy_or_sell_choice.Buy, num)})
                if shares == 0: self.max_price = today_price

        return choices
