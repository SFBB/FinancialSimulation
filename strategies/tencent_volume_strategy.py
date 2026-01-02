from utility.strategy import strategy_base, buy_or_sell_choice, MarketConfig
from utility.stock_util import extract_close_price
import numpy as np
import pandas as pd
import datetime

class Tencent_Volume_Sniper_Strategy(strategy_base):
    """
    Tencent (0700.HK) Volume Volatility Sniper
    ------------------------------------------
    Exploits the "Calm before the Storm" phenomenon in Volume.
    
    Logic:
    1. Monitor Volume Volatility (CV = StdDev / Mean).
    2. Setup: Wait for CV to drop below 'calm_threshold' (Market is asleep/accumulating).
    3. Trigger: Buy on first Volume Spike (Vol > 1.5x Avg) AND Price Up.
    4. Exit: Trailing Stop or if Volume Volatility explodes (Distribution).
    """

    def __init__(
        self,
        ticker="0700.HK",
        initial_money=1000000,
        vol_window=20,      # Lookback for volume stats
        calm_threshold=0.3, # CV < 0.3 means very stable volume
        spike_multiplier=1.5, # Volume > 1.5x Avg to trigger
        stop_loss_pct=0.08
    ):
        # HK Market: T+0, Stamp Duty 0.1% (higher than US/CN)
        # We simulate with US_Market config but slightly higher slippage/cost if needed
        # Or define HK_Market. Let's use US T+0 logic for simplicity as HK is T+0.
        super().__init__()
        
        self.stock_names = [ticker]
        self.ticker = ticker
        self.initial_money = initial_money
        
        self.vol_window = vol_window
        self.calm_threshold = calm_threshold
        self.spike_multiplier = spike_multiplier
        self.stop_loss_pct = stop_loss_pct
        
        self.max_price = 0
        self.state = "WAIT" # WAIT -> READY -> HOLD

    def get_name(self):
        return f"Tencent_VolSniper(CV{self.calm_threshold}_Spike{self.spike_multiplier})"

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
        if len(hist) < self.vol_window + 5: return choices
        
        # --- Volume Indicators ---
        volumes = hist['volume']
        closes = hist['close']
        
        # Rolling stats
        vol_mean = volumes.rolling(window=self.vol_window).mean().iloc[-1]
        vol_std = volumes.rolling(window=self.vol_window).std().iloc[-1]
        
        if vol_mean == 0: return choices
        
        # Coefficient of Variation (CV)
        vol_cv = vol_std / vol_mean
        
        current_vol = volumes.iloc[-1]
        is_price_up = closes.iloc[-1] > closes.iloc[-2]
        
        action = "HOLD"
        
        # === State Machine ===
        
        if shares == 0:
            # State 1: WAIT -> READY
            # If Volume is super calm (Low CV), we get READY.
            if vol_cv < self.calm_threshold:
                self.state = "READY"
            
            # State 2: READY -> BUY
            # If we are READY (recent calm) AND Volume Spikes + Price Up
            # Note: We need to remember "READY" status? 
            # Ideally, the "Calm" condition should be true RECENTLY (e.g. within last 5 days).
            # Simplified: If CV is low NOW, or was low very recently.
            
            # Let's check if we are in a low-vol regime
            is_low_vol_regime = vol_cv < self.calm_threshold
            
            if is_low_vol_regime:
                # We are in the quiet zone. Waiting for the bang.
                pass
            
            # Trigger: Volume Spike
            # But the spike itself will increase Volatility! 
            # So CV might jump up today.
            # We check if yesterday's CV was low.
            prev_cv = (volumes.rolling(window=self.vol_window).std() / volumes.rolling(window=self.vol_window).mean()).iloc[-2]
            
            if prev_cv < self.calm_threshold:
                # Yesterday was calm.
                if current_vol > vol_mean * self.spike_multiplier and is_price_up:
                    action = "BUY"
        
        elif shares > 0:
            # Exit Logic
            self.max_price = max(self.max_price, today_price)
            if today_price < self.max_price * (1 - self.stop_loss_pct):
                action = "SELL"
            
            # Volatility Exit: If Volume goes crazy (CV > 0.8) and Price drops
            if vol_cv > 0.8 and not is_price_up:
                action = "SELL"

        # === Execution ===
        if action == "SELL":
            choices.append({self.ticker: (buy_or_sell_choice.Sell, shares)})
            self.max_price = 0
            
        elif action == "BUY":
            num = (cash * 0.99) / today_price
            choices.append({self.ticker: (buy_or_sell_choice.Buy, num)})
            self.max_price = today_price

        return choices
