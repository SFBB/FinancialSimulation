from utility.strategy import strategy_base, buy_or_sell_choice
from utility.stock_util import extract_close_price
from utility.math_util import math_util
import numpy as np
import pandas as pd
import datetime

class AAPL_Sniper_Strategy(strategy_base):
    """
    AAPL Sniper Strategy
    --------------------
    Philosophy: "Buy the dip in a Bull Market, Lock profits tight at the top."
    
    1. Filter: Price > EMA 200 (Only trade in long-term Bull Trends).
    2. Entry (The Sniper): Buy when RSI < 40 (Oversold Dip).
    3. Exit (The Profit Locker):
       - Dynamic Chandelier Exit (ATR Trailing Stop).
       - Normal Mode: Stop = High - 3.5 * ATR (Give room to grow).
       - Profit Mode (RSI > 75): Stop = High - 1.5 * ATR (Tighten to lock gains).
    """

    def __init__(
        self,
        ticker="AAPL",
        initial_money=1000000,
        trend_ma=200,      # Long term bull filter
        entry_rsi=40,      # Buy the dip threshold
        profit_rsi=75,     # Overbought threshold to tighten stop
        atr_window=14,     # Volatility measurement
        stop_atr_wide=3.5, # Wide stop for riding trends
        stop_atr_tight=1.5 # Tight stop for locking profits
    ):
        super().__init__()
        self.stock_names = [ticker]
        self.ticker = ticker
        self.initial_money = initial_money
        
        self.trend_ma = trend_ma
        self.entry_rsi = entry_rsi
        self.profit_rsi = profit_rsi
        self.atr_window = atr_window
        self.stop_atr_wide = stop_atr_wide
        self.stop_atr_tight = stop_atr_tight
        
        # Internal State
        self.highest_price = 0
        self.trailing_stop_price = 0
        self.mode = "WAIT" # WAIT, HOLD, PROTECT

    def get_name(self):
        return f"AAPL_Sniper_RSI{self.entry_rsi}_{self.profit_rsi}_ATR{self.stop_atr_wide}_{self.stop_atr_tight}"

    def get_stock_source(self, stock_name):
        return "yahoo"

    def calculate_indicators(self, prices):
        s = pd.Series(prices)
        
        # 1. Trend (EMA 200)
        ema_trend = s.ewm(span=self.trend_ma, adjust=False).mean().iloc[-1]
        
        # 2. RSI (14)
        delta = s.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        return ema_trend, rsi

    def _calculate_atr(self, history, window):
        high = history['high'] if 'high' in history.columns else history['close']
        low = history['low'] if 'low' in history.columns else history['close']
        close = history['close']
        prev_close = close.shift(1)
        
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=window).mean().iloc[-1]
        return atr

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        stock_data = self.latest_stocks_info[self.ticker]
        today_price = extract_close_price(stock_data, self.today_time)

        if today_price is None or np.isnan(today_price):
            return choices

        # 0. Asset Update
        shares = self.hold_stock_number.get(self.ticker, 0)
        cash = self.initial_money + self.changed_money
        total_equity = cash + (shares * today_price)
        
        if total_equity <= 0: return choices

        # 1. Get History & Indicators
        hist = stock_data.get_history_price(self.today_time)
        closes = hist["close"]
        
        if len(closes) < self.trend_ma + 10:
            return choices
            
        ema_trend, current_rsi = self.calculate_indicators(closes.values)
        current_atr = self._calculate_atr(hist, self.atr_window)
        
        # 2. Strategy Logic
        
        action = "HOLD"
        
        if shares == 0:
            # === ENTRY LOGIC ===
            # Condition 1: Bull Market Regime (Price > EMA 200)
            is_bull_market = today_price > ema_trend
            
            # Condition 2: Deep Dip (RSI < 40)
            # This is the "Sniper" shot. Catching the fear.
            is_oversold = current_rsi < self.entry_rsi
            
            if is_bull_market and is_oversold:
                action = "BUY"
                self.highest_price = today_price
                # Initialize stop loss (Wide)
                self.trailing_stop_price = today_price - (self.stop_atr_wide * current_atr)
                self.mode = "HOLD"

        elif shares > 0:
            # === EXIT / MANAGEMENT LOGIC ===
            
            # A. Update Highest Price (Trailing mechanism)
            if today_price > self.highest_price:
                self.highest_price = today_price
                
            # B. Dynamic Stop Loss Adjustment
            # If RSI is super high (>75), we are in "Euphoria" zone.
            # We tighten the stop to lock in profits.
            if current_rsi > self.profit_rsi:
                self.mode = "PROTECT"
                # Tight Stop
                new_stop = self.highest_price - (self.stop_atr_tight * current_atr)
            else:
                self.mode = "HOLD"
                # Wide Stop (Standard Trend Following)
                new_stop = self.highest_price - (self.stop_atr_wide * current_atr)
            
            # Never move stop loss DOWN (Ratchet)
            self.trailing_stop_price = max(self.trailing_stop_price, new_stop)
            
            # C. Check Stop Trigger
            if today_price < self.trailing_stop_price:
                action = "SELL"
                # Also, if Trend breaks (Price < EMA 200), we get out regardless of ATR
                # This protects against Long Term Bear Markets
            elif today_price < ema_trend:
                action = "SELL"

        # 3. Execution
        if action == "BUY":
            # 99% position (Sniper takes full shot)
            number = (cash * 0.99) / today_price
            choices.append({self.ticker: (buy_or_sell_choice.Buy, number)})
            
        elif action == "SELL":
            choices.append({self.ticker: (buy_or_sell_choice.Sell, shares)})
            self.highest_price = 0
            self.trailing_stop_price = 0
            self.mode = "WAIT"

        return choices


class AAPL_Sniper_Hybrid_Strategy(strategy_base):
    """
    AAPL Sniper Hybrid Strategy (Sniper Entry + V3 Vol Sizing)
    ----------------------------------------------------------
    Combines the best of both worlds:
    1. Sniper Entry: High precision RSI Dips in Bull Trends.
    2. V3 Sizing: Volatility Targeting + Macro Risk to cushion drawdowns.
    3. Sniper Exit: Dynamic ATR Trailing Stop (Best for locking profits).
    """

    def __init__(
        self,
        ticker="AAPL",
        initial_money=1000000,
        trend_ma=200,       # Long term bull filter
        entry_rsi=45,       # Buy the dip
        profit_rsi=80,      # Euphoria threshold
        atr_window=14,
        stop_atr_wide=3.0,
        stop_atr_tight=1.0,
        target_vol=0.35,    # V3: Volatility Target
        macro_ma=50         # V3: Macro Filter
    ):
        super().__init__()
        self.stock_names = [ticker]
        self.ticker = ticker
        self.initial_money = initial_money
        
        self.trend_ma = trend_ma
        self.entry_rsi = entry_rsi
        self.profit_rsi = profit_rsi
        self.atr_window = atr_window
        self.stop_atr_wide = stop_atr_wide
        self.stop_atr_tight = stop_atr_tight
        self.target_vol = target_vol
        self.macro_ma = macro_ma
        
        self.highest_price = 0
        self.trailing_stop_price = 0
        self.mode = "WAIT" 

    def get_name(self):
        return f"AAPL_Hybrid_SniperVol_RSI{self.entry_rsi}_Vol{self.target_vol}"

    def get_stock_source(self, stock_name):
        return "yahoo"

    def _get_macro_risk(self):
        # V3 Macro Logic
        risk_level = 0
        oil_info = self.latest_economics_info.get('oil')
        if oil_info:
            oil_hist = oil_info.get_history_info(self.today_time, datetime.timedelta(days=self.macro_ma * 2 + 30))
            if oil_hist is not None and not oil_hist.empty:
                prices = oil_hist['Close'] if 'Close' in oil_hist.columns else oil_hist.get('close')
                if prices is not None and len(prices) > self.macro_ma:
                    sma = prices.rolling(window=self.macro_ma).mean().iloc[-1]
                    curr = prices.iloc[-1]
                    if curr > sma * 1.05: risk_level += 1

        debt_info = self.latest_economics_info.get('us_debt')
        if debt_info:
            debt_hist = debt_info.get_history_info(self.today_time, datetime.timedelta(days=self.macro_ma * 2 + 30))
            if debt_hist is not None and not debt_hist.empty:
                prices = debt_hist['Close'] if 'Close' in debt_hist.columns else debt_hist.get('close')
                if prices is not None and len(prices) > self.macro_ma:
                    sma = prices.rolling(window=self.macro_ma).mean().iloc[-1]
                    curr = prices.iloc[-1]
                    if curr > sma * 1.05: risk_level += 1
        
        if risk_level >= 2: return 0.4 
        if risk_level == 1: return 0.7
        return 1.0

    def _calculate_indicators(self, prices, history):
        s = pd.Series(prices)
        ema_trend = s.ewm(span=self.trend_ma, adjust=False).mean().iloc[-1]
        
        delta = s.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        # ATR
        high = history['high'] if 'high' in history.columns else history['close']
        low = history['low'] if 'low' in history.columns else history['close']
        prev_close = history['close'].shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_window).mean().iloc[-1]
        
        return ema_trend, rsi, atr

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
        closes = hist["close"]
        if len(closes) < self.trend_ma + 10: return choices

        ema_trend, current_rsi, current_atr = self._calculate_indicators(closes.values, hist)
        
        # === 1. Calculate Target Exposure (The V3 Brain) ===
        # Volatility Sizing
        returns = closes.pct_change().dropna()
        realized_vol = returns.tail(20).std() * np.sqrt(252)
        if realized_vol == 0: realized_vol = 0.01
        
        vol_scalar = self.target_vol / realized_vol
        vol_scalar = min(vol_scalar, 1.0) # Cap at 1.0
        
        # Macro Sizing
        macro_mult = self._get_macro_risk()
        
        # Final Target Pct (Ideally)
        ideal_target_pct = 1.0 * vol_scalar * macro_mult
        
        # === 2. Logic Control (The Sniper Trigger) ===
        action = "HOLD"
        
        if shares == 0:
            # Entry: Bull Market + Dip
            if today_price > ema_trend and current_rsi < self.entry_rsi:
                action = "BUY"
                self.highest_price = today_price
                self.trailing_stop_price = today_price - (self.stop_atr_wide * current_atr)

        elif shares > 0:
            # Exit Logic (Sniper Protect)
            
            # Update High
            self.highest_price = max(self.highest_price, today_price)
            
            # Dynamic Stop
            if current_rsi > self.profit_rsi:
                # Tighten
                new_stop = self.highest_price - (self.stop_atr_tight * current_atr)
            else:
                # Normal
                new_stop = self.highest_price - (self.stop_atr_wide * current_atr)
            
            self.trailing_stop_price = max(self.trailing_stop_price, new_stop)
            
            if today_price < self.trailing_stop_price or today_price < ema_trend:
                action = "SELL"
            else:
                action = "REBALANCE" # Stay in, but adjust size

        # === 3. Execution ===
        if action == "SELL":
            choices.append({self.ticker: (buy_or_sell_choice.Sell, shares)})
            self.highest_price = 0
            self.trailing_stop_price = 0
            
        elif action == "BUY" or action == "REBALANCE":
            # For BUY, we enter with ideal_target_pct
            # For REBALANCE, we adjust to ideal_target_pct
            
            target_value = total_equity * ideal_target_pct
            current_value = shares * today_price
            diff_value = target_value - current_value
            
            # Threshold to avoid over-trading (5%)
            if abs(diff_value) > total_equity * 0.05 or (action == "BUY"):
                if diff_value > 0:
                    num = diff_value / today_price
                    choices.append({self.ticker: (buy_or_sell_choice.Buy, num)})
                elif diff_value < 0:
                    num = abs(diff_value) / today_price
                    choices.append({self.ticker: (buy_or_sell_choice.Sell, num)})

        return choices