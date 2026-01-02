from utility.strategy import strategy_base, buy_or_sell_choice, MarketConfig
from utility.stock_util import extract_close_price
import numpy as np
import pandas as pd
import datetime

class Moutai_Valuation_Strategy(strategy_base):
    """
    Moutai Valuation Strategy (PE + Trend)
    --------------------------------------
    Uses Fundamental Valuation (PE TTM) to determine regime.
    
    Logic:
    1. Undervalued (PE < 30): Accumulate aggressively if trend stabilizes (Price > EMA 20).
    2. Overvalued (PE > 50): Distribute/Sell.
    3. Fair Value (30 < PE < 50): Hold / Trend Follow.
    
    Data Source: AKShare (PE TTM)
    """

    def __init__(
        self,
        ticker="600519.SS",
        initial_money=1000000,
        buy_pe=35,       # Relaxed slightly from 30 to catch more bottoms
        sell_pe=55,      # Relaxed slightly from 50 to ride bubbles
        trend_ma=20,     # Short term trend confirmation
        stop_loss_pct=0.10
    ):
        super().__init__(market_config=MarketConfig.CN_Market())
        
        self.stock_names = [ticker]
        self.ticker = ticker
        self.initial_money = initial_money
        
        self.buy_pe = buy_pe
        self.sell_pe = sell_pe
        self.trend_ma = trend_ma
        self.stop_loss_pct = stop_loss_pct
        
        self.max_price = 0

    def get_name(self):
        return f"Moutai_Valuation(BuyPE{self.buy_pe}_SellPE{self.sell_pe})"

    def get_stock_source(self, stock_name):
        # Fallback to Yahoo (Calculated PE) since AKShare is unstable in this env
        return "yahoo" 

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        stock_data = self.latest_stocks_info[self.ticker]
        today_price = extract_close_price(stock_data, self.today_time)
        
        if today_price is None or np.isnan(today_price): return choices

        # 0. Asset Update
        shares = self.hold_stock_number.get(self.ticker, 0)
        frozen = self.frozen_stock.get(self.ticker, 0)
        sellable = shares - frozen
        
        cash = self.initial_money + self.changed_money
        total_equity = cash + (shares * today_price)
        
        if total_equity <= 0: return choices

        # 1. Get History & Indicators
        hist = stock_data.get_history_price(self.today_time)
        if len(hist) < self.trend_ma + 5: return choices
        
        # Check for PE Data
        current_pe = np.nan
        if 'pe_ttm' in hist.columns:
            current_pe = hist['pe_ttm'].iloc[-1]
        elif 'pe' in hist.columns:
            current_pe = hist['pe'].iloc[-1]
            
        # Fallback if PE is missing (e.g. data source failure)
        # If missing, we can default to Trend Following or Hold
        has_pe = not np.isnan(current_pe) and current_pe > 0
        
        # Debug PE values
        if self.today_time.day == 1 and self.today_time.month == 1:
             print(f"Date: {self.today_time.date()}, Price: {today_price:.2f}, PE: {current_pe}")
        
        # Trend
        ema_trend = hist['close'].ewm(span=self.trend_ma, adjust=False).mean().iloc[-1]
        is_uptrend = today_price > ema_trend
        
        action = "HOLD"
        
        # === SELL LOGIC ===
        if sellable > 0:
            # Stop Loss (Safety Net)
            self.max_price = max(self.max_price, today_price)
            if today_price < self.max_price * (1 - self.stop_loss_pct):
                action = "SELL"
            
            # Valuation Exit
            elif has_pe and current_pe > self.sell_pe:
                # Bubble territory! Sell.
                action = "SELL"
                
        # === BUY LOGIC ===
        if action != "SELL":
            if has_pe and current_pe < self.buy_pe:
                # Cheap!
                if is_uptrend:
                    # Cheap + Stabilized -> Buy Aggressively
                    action = "BUY"
                else:
                    # Cheap but falling -> Wait (Don't catch knife)
                    pass
            elif shares == 0:
                # If we have no position, but PE is reasonable (Fair Value) and Trending Up
                # Maybe enter a small position? Or just wait for deep value?
                # Let's stick to Deep Value investing for this strategy.
                pass

        # === EXECUTION ===
        if action == "SELL" and sellable > 0:
            choices.append({self.ticker: (buy_or_sell_choice.Sell, sellable)})
            self.max_price = 0
            
        elif action == "BUY":
            # Target 100% (High conviction on value)
            target_val = total_equity * 1.0
            current_val = shares * today_price
            diff = target_val - current_val
            
            if diff > total_equity * 0.1: # Threshold
                num = diff / today_price
                num = int(num / 100) * 100
                if num > 0:
                    choices.append({self.ticker: (buy_or_sell_choice.Buy, num)})
                    if shares == 0: self.max_price = today_price

        return choices
