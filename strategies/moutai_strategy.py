from utility.strategy import strategy_base, buy_or_sell_choice, MarketConfig
from utility.stock_util import extract_close_price
from utility.math_util import math_util
import numpy as np
import pandas as pd
import datetime

# Re-implementing the V3 logic specifically for Moutai (CN Market)
class Moutai_FMH_V3_Strategy(strategy_base):
    """
    Moutai FMH V3 Strategy (Adapted for A-Shares)
    ---------------------------------------------
    Uses the successful FMH + Volatility Targeting logic.
    Adapts for T+1 Settlement and A-Share Volatility.
    """

    def __init__(
        self,
        ticker="600519.SS",
        initial_money=1000000,
        hurst_threshold=0.55,
        hurst_window=100,
        regime_ma=60,      # Faster regime for A-shares (2021 crash was fast)
        target_vol=0.25,   # Lower vol target (A-shares limit up/down is 10%, effectively capping realized vol)
        macro_ma=50,
        stop_loss_pct=0.08
    ):
        # Enforce CN Market (T+1, Tax)
        super().__init__(market_config=MarketConfig.CN_Market())
        
        self.stock_names = [ticker]
        self.ticker = ticker
        self.initial_money = initial_money
        
        self.hurst_threshold = hurst_threshold
        self.hurst_window = hurst_window
        self.regime_ma = regime_ma
        self.target_vol = target_vol
        self.macro_ma = macro_ma
        self.stop_loss_pct = stop_loss_pct
        
        self.max_price = 0
        self.cooldown_counter = 0

    def get_name(self):
        return f"Moutai_FMH_V3(H{self.hurst_threshold}_Vol{self.target_vol})"

    def get_stock_source(self, stock_name):
        return "yahoo"

    # Reuse the exact same logic as AAPL V3, but self.market_config handles the T+1 constraints automatically
    
    def _get_macro_risk(self):
        # Ideally we should use CHINA Macro (e.g. SHIBOR, CNY/USD). 
        # But for now, we assume Global Risk (Oil/US Rates) also affects China assets via foreign capital flows.
        # Or we can disable it if we think Moutai is immune.
        # Let's keep it but maybe relax it.
        return 1.0 # Disabling Macro for now to isolate pure Price Trend performance on Moutai

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        stock_data = self.latest_stocks_info[self.ticker]
        today_price = extract_close_price(stock_data, self.today_time)
        if today_price is None or np.isnan(today_price): return choices

        shares = self.hold_stock_number.get(self.ticker, 0)
        
        # T+1 Check: logic in strategy_base handles execution refusal, 
        # but here we should know how many we CAN sell to avoid generating invalid signals.
        frozen = self.frozen_stock.get(self.ticker, 0)
        sellable = shares - frozen
        
        cash = self.initial_money + self.changed_money
        total_equity = cash + (shares * today_price)
        if total_equity <= 0: return choices

        # Risk Management
        if self.cooldown_counter > 0:
            self.cooldown_counter -= 1
            if sellable > 0:
                 choices.append({self.ticker: (buy_or_sell_choice.Sell, sellable)})
            return choices
            
        if sellable > 0:
            self.max_price = max(self.max_price, today_price)
            if today_price < self.max_price * (1 - self.stop_loss_pct):
                choices.append({self.ticker: (buy_or_sell_choice.Sell, sellable)})
                self.max_price = 0
                self.cooldown_counter = 5
                return choices

        # Calculations
        hist = stock_data.get_history_price(self.today_time)
        closes = hist["close"].values
        if len(closes) < max(self.hurst_window, self.regime_ma) + 10: return choices

        # Volatility
        returns = pd.Series(closes).pct_change().dropna()
        if len(returns) < 20: return choices
        realized_vol = returns.tail(20).std() * np.sqrt(252)
        if realized_vol == 0: realized_vol = 0.01
        
        vol_scalar = self.target_vol / realized_vol
        vol_scalar = min(vol_scalar, 1.0) 

        # Regime
        ema_regime = pd.Series(closes).ewm(span=self.regime_ma, adjust=False).mean().iloc[-1]
        is_bull_regime = today_price > ema_regime
        
        # Hurst
        H, _ = math_util.rs_analysis_scientific(closes[-self.hurst_window:])
        is_trending = H > self.hurst_threshold
        
        target_pct = 0.0
        
        if is_bull_regime:
            if is_trending:
                target_pct = 1.0 * vol_scalar 
            else:
                target_pct = 0.6 * vol_scalar 
        else:
            # Bear Regime
            if H > 0.65: # Strong contrarian trend
                 target_pct = 0.3 * vol_scalar
            else:
                 target_pct = 0.0
                 self.max_price = 0
            
        # Execution
        target_value = total_equity * target_pct
        current_value = shares * today_price
        diff_value = target_value - current_value
        
        # A-Share 100 lot size adjustment
        if abs(diff_value) > total_equity * 0.05 or (shares == 0 and target_pct > 0) or (target_pct == 0 and shares > 0):
            if diff_value > 0:
                num = diff_value / today_price
                num = int(num / 100) * 100 # Floor to 100
                if num > 0:
                    choices.append({self.ticker: (buy_or_sell_choice.Buy, num)})
                    if shares == 0: self.max_price = today_price
            elif diff_value < 0:
                num = abs(diff_value) / today_price
                num = int(num / 100) * 100 
                # Cap at sellable
                num = min(num, sellable)
                if num > 0:
                    choices.append({self.ticker: (buy_or_sell_choice.Sell, num)})
                
        return choices
