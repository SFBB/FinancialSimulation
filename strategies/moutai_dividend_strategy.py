from utility.strategy import strategy_base, buy_or_sell_choice, MarketConfig
from utility.stock_util import extract_close_price
import numpy as np
import pandas as pd
import datetime

class Moutai_Dividend_Strategy(strategy_base):
    """
    Moutai Dividend Yield Strategy (Valuation Proxy)
    ------------------------------------------------
    Uses Trailing 12M Dividend Yield to proxy valuation.
    Works because Dividends are 'Real Cash' and data is available historically.
    
    Logic:
    1. Calculate TTM Dividends (Sum of dividends in last 365 days).
    2. Calculate Yield = TTM Dividends / Current Price.
    3. Buy when Yield > 2.0% (Cheap / High Margin of Safety).
    4. Sell when Yield < 1.0% (Expensive / Bubble).
    """

    def __init__(
        self,
        ticker="600519.SS",
        initial_money=1000000,
        buy_yield=0.020,  # > 2.0% Yield
        sell_yield=0.010, # < 1.0% Yield
        trend_ma=20,
        stop_loss_pct=0.10
    ):
        super().__init__(market_config=MarketConfig.CN_Market())
        
        self.stock_names = [ticker]
        self.ticker = ticker
        self.initial_money = initial_money
        
        self.buy_yield = buy_yield
        self.sell_yield = sell_yield
        self.trend_ma = trend_ma
        self.stop_loss_pct = stop_loss_pct
        
        self.max_price = 0

    def get_name(self):
        return f"Moutai_DivYield(Buy{self.buy_yield*100:.1f}%_Sell{self.sell_yield*100:.1f}%)"

    def get_stock_source(self, stock_name):
        return "yahoo" # Needs yfinance for dividends

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        stock_data = self.latest_stocks_info[self.ticker]
        today_price = extract_close_price(stock_data, self.today_time)
        
        if today_price is None or np.isnan(today_price): return choices

        shares = self.hold_stock_number.get(self.ticker, 0)
        frozen = self.frozen_stock.get(self.ticker, 0)
        sellable = shares - frozen
        
        cash = self.initial_money + self.changed_money
        total_equity = cash + (shares * today_price)
        if total_equity <= 0: return choices

        # Get History
        hist = stock_data.get_history_price(self.today_time)
        if len(hist) < 365: return choices
        
        # --- Calculate Dividend Yield ---
        # Dividends column check
        current_yield = 0.0
        if 'dividends' in hist.columns:
            # Sum dividends over last 1 year (approx 252 trading days or by date)
            # Since index is date, we can filter by date
            one_year_ago = self.today_time - datetime.timedelta(days=365)
            mask = hist.index >= pd.Timestamp(one_year_ago.date())
            ttm_divs = hist.loc[mask, 'dividends'].sum()
            
            if ttm_divs > 0:
                current_yield = ttm_divs / today_price
        
        # Trend
        ema_trend = hist['close'].ewm(span=self.trend_ma, adjust=False).mean().iloc[-1]
        is_uptrend = today_price > ema_trend
        
        # Debug Yield (First day of year)
        if self.today_time.day == 1 and self.today_time.month == 1:
             print(f"Date: {self.today_time.date()}, Price: {today_price:.2f}, Divs(TTM): {ttm_divs:.2f}, Yield: {current_yield*100:.2f}%")

        action = "HOLD"
        
        # === SELL LOGIC ===
        if sellable > 0:
            self.max_price = max(self.max_price, today_price)
            if today_price < self.max_price * (1 - self.stop_loss_pct):
                action = "SELL"
            elif current_yield < self.sell_yield and current_yield > 0: # Only sell if valid yield
                # Yield too low (Price too high) -> Bubble
                action = "SELL"
                
        # === BUY LOGIC ===
        if action != "SELL":
            # Buy if Yield is High (Cheap) AND Trend is Up (Don't catch knife)
            if current_yield > self.buy_yield and is_uptrend:
                action = "BUY"

        # === EXECUTION ===
        if action == "SELL" and sellable > 0:
            choices.append({self.ticker: (buy_or_sell_choice.Sell, sellable)})
            self.max_price = 0
            
        elif action == "BUY":
            target_val = total_equity * 1.0
            current_val = shares * today_price
            diff = target_val - current_val
            
            if diff > total_equity * 0.1:
                num = diff / today_price
                num = int(num / 100) * 100
                if num > 0:
                    choices.append({self.ticker: (buy_or_sell_choice.Buy, num)})
                    if shares == 0: self.max_price = today_price

        return choices
