from utility.strategy import strategy_base, buy_or_sell_choice
from utility.stock_util import extract_close_price
import numpy as np
import pandas as pd
import datetime

class AAPL_PEG_Strategy(strategy_base):
    """
    AAPL PEG Strategy (Lynch Style)
    -------------------------------
    PEG = PE Ratio / Earnings Growth Rate
    
    Logic:
    1. Reverse engineer TTM EPS from Price and PE.
    2. Calculate YoY Earnings Growth (G).
    3. Buy when PEG < 1.5 (Growth is cheap).
    4. Sell when PEG > 2.5 (Growth is expensive).
    5. Trend Filter: Price > EMA 50 (Avoid Value Traps).
    """

    def __init__(
        self,
        ticker="AAPL",
        initial_money=1000000,
        buy_peg=1.5,
        sell_peg=2.5,
        trend_ma=50,
        stop_loss_pct=0.10
    ):
        super().__init__()
        self.stock_names = [ticker]
        self.ticker = ticker
        self.initial_money = initial_money
        
        self.buy_peg = buy_peg
        self.sell_peg = sell_peg
        self.trend_ma = trend_ma
        self.stop_loss_pct = stop_loss_pct
        
        self.max_price = 0

    def get_name(self):
        return f"AAPL_PEG(Buy{self.buy_peg}_Sell{self.sell_peg})"

    def get_stock_source(self, stock_name):
        return "yahoo" # Needs yfinance for PE calc

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        stock_data = self.latest_stocks_info[self.ticker]
        today_price = extract_close_price(stock_data, self.today_time)
        
        if today_price is None or np.isnan(today_price): return choices

        shares = self.hold_stock_number.get(self.ticker, 0)
        cash = self.initial_money + self.changed_money
        total_equity = cash + (shares * today_price)
        if total_equity <= 0: return choices

        # Get History
        # We need at least 1 year + buffer to calculate YoY Growth
        hist = stock_data.get_history_price(self.today_time)
        if len(hist) < 300: return choices
        
        # Check PE Data
        current_pe = np.nan
        # Ensure we check lowercase columns as normalized by stock_util
        if 'pe_ttm' in hist.columns:
            current_pe = hist['pe_ttm'].iloc[-1]
        elif 'pe' in hist.columns:
            current_pe = hist['pe'].iloc[-1]
            
        action = "HOLD"
        
        # Calculate PEG if PE exists
        current_peg = np.nan
        growth_rate = 0.0
        
        if not np.isnan(current_pe) and current_pe > 0:
            # 1. Reverse Engineer Implied EPS History
            # Implied EPS = Close / PE
            # Note: We need the SERIES of PE and Close to calculate Growth
            
            # Extract historical PE and Close
            # Be careful with mismatched indices or NaNs
            if 'pe_ttm' in hist.columns:
                pe_series = hist['pe_ttm']
            else:
                pe_series = hist['pe']
                
            close_series = hist['close']
            
            # Implied EPS Series
            eps_series = close_series / pe_series
            
            # 2. Calculate YoY Growth (approx 252 days ago)
            # Use a rolling mean of EPS to smooth out daily price noise in the reverse calculation
            # eps_series = eps_series.rolling(window=20).mean()
            
            if len(eps_series) > 260:
                eps_now = eps_series.iloc[-1]
                eps_prev_year = eps_series.iloc[-252]
                
                if eps_prev_year > 0:
                    growth_rate = (eps_now - eps_prev_year) / eps_prev_year
                    # Growth Rate in PEG formula is usually whole number (e.g. 20 for 20%)
                    growth_num = growth_rate * 100
                    
                    if growth_num > 0:
                        current_peg = current_pe / growth_num
        
        # Trend
        ema_trend = hist['close'].ewm(span=self.trend_ma, adjust=False).mean().iloc[-1]
        is_uptrend = today_price > ema_trend
        
        # Debug PEG (First day of year)
        if self.today_time.day == 1 and self.today_time.month == 1:
             print(f"Date: {self.today_time.date()} | Price: {today_price:.0f} | PE: {current_pe:.1f} | Growth: {growth_rate*100:.1f}% | PEG: {current_peg:.2f}")

        # === SELL LOGIC ===
        if shares > 0:
            self.max_price = max(self.max_price, today_price)
            # Stop Loss
            if today_price < self.max_price * (1 - self.stop_loss_pct):
                action = "SELL"
            # Valuation Sell
            elif not np.isnan(current_peg) and current_peg > self.sell_peg:
                action = "SELL"
                
        # === BUY LOGIC ===
        if action != "SELL":
            if not np.isnan(current_peg) and current_peg > 0 and current_peg < self.buy_peg:
                # Undervalued relative to growth
                if is_uptrend:
                    action = "BUY"

        # === EXECUTION ===
        if action == "SELL" and shares > 0:
            choices.append({self.ticker: (buy_or_sell_choice.Sell, shares)})
            self.max_price = 0
            
        elif action == "BUY":
            target_val = total_equity * 1.0
            current_val = shares * today_price
            diff = target_val - current_val
            
            if diff > total_equity * 0.1:
                num = diff / today_price
                choices.append({self.ticker: (buy_or_sell_choice.Buy, num)})
                if shares == 0: self.max_price = today_price

        return choices
