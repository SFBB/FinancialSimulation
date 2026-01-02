from utility.strategy import strategy_base, buy_or_sell_choice
from utility.stock_util import extract_close_price
from utility.math_util import math_util
import numpy as np
import pandas as pd
import datetime

class AAPL_Ultimate_Strategy(strategy_base):
    """
    AAPL Ultimate All-Weather Strategy
    ----------------------------------
    Integrates Macro, Fundamental (Div Growth), and Technical (FMH+Vol) factors.
    
    1. Regime (Macro): Oil/Rates check. Sets maximum exposure ceiling.
    2. Core (Fundamental): Chowder Score (Yield + Growth). Provides baseline allocation.
       - Adaptive: If no dividends (pre-2012), relies on Technicals.
    3. Satellite (Technical): FMH Trend + Volatility Targeting. Provides dynamic allocation.
    
    Target: Outperform SPY (Alpha), Maximize Sharpe, Minimize Drawdown.
    """

    def __init__(
        self,
        ticker="AAPL",
        initial_money=1000000,
        # Fundamental (Chowder)
        buy_score=12.0,
        sell_score=8.0,
        # Technical (FMH V3)
        hurst_threshold=0.55,
        hurst_window=100,
        regime_ma=100,
        target_vol=0.35, # Aggressive vol target
        # Macro
        macro_ma=50,
        stop_loss_pct=0.10
    ):
        super().__init__()
        self.stock_names = [ticker]
        self.ticker = ticker
        self.initial_money = initial_money
        
        self.buy_score = buy_score
        self.sell_score = sell_score
        self.hurst_threshold = hurst_threshold
        self.hurst_window = hurst_window
        self.regime_ma = regime_ma
        self.target_vol = target_vol
        self.macro_ma = macro_ma
        self.stop_loss_pct = stop_loss_pct
        
        self.max_price = 0
        self.cooldown_counter = 0

    def get_name(self):
        return f"{self.ticker}_Ultimate_Macro_Fund_Tech"

    def get_stock_source(self, stock_name):
        return "yahoo"

    def _get_macro_ceiling(self):
        """
        Returns max allocation (0.0 to 1.0) based on Macro Environment.
        """
        risk_level = 0
        # Oil
        oil_info = self.latest_economics_info.get('oil')
        if oil_info:
            oil_hist = oil_info.get_history_info(self.today_time, datetime.timedelta(days=self.macro_ma * 2 + 30))
            if oil_hist is not None and not oil_hist.empty:
                col = 'Close' if 'Close' in oil_hist.columns else 'close'
                if col in oil_hist.columns:
                    prices = oil_hist[col]
                    if len(prices) > self.macro_ma:
                        sma = prices.rolling(window=self.macro_ma).mean().iloc[-1]
                        curr = prices.iloc[-1]
                        if curr > sma * 1.05: risk_level += 1

        # Debt
        debt_info = self.latest_economics_info.get('us_debt')
        if debt_info:
            debt_hist = debt_info.get_history_info(self.today_time, datetime.timedelta(days=self.macro_ma * 2 + 30))
            if debt_hist is not None and not debt_hist.empty:
                col = 'Close' if 'Close' in debt_hist.columns else 'close'
                if col in debt_hist.columns:
                    prices = debt_hist[col]
                    if len(prices) > self.macro_ma:
                        sma = prices.rolling(window=self.macro_ma).mean().iloc[-1]
                        curr = prices.iloc[-1]
                        if curr > sma * 1.05: risk_level += 1
        
        # Risk Ceiling
        if risk_level >= 2: return 0.5 # Serious Macro Headwinds -> Max 50% Exposure
        if risk_level == 1: return 0.8 # Moderate Risk -> Max 80%
        return 1.0 # Blue Sky -> Max 100%

    def _get_fundamental_score(self, hist, price):
        """
        Returns Chowder Score. 
        If no dividend history (pre-2012 for AAPL), returns None (Neutral).
        """
        if 'dividends' not in hist.columns: return None
        
        # Need 5 years for Growth
        # Relaxed: If we have at least 1 year dividends, we can calc Yield.
        # Growth needs 5 years.
        
        one_year_ago = self.today_time - datetime.timedelta(days=365)
        mask_ttm = hist.index >= pd.Timestamp(one_year_ago.date())
        ttm_divs = hist.loc[mask_ttm, 'dividends'].sum()
        
        if ttm_divs == 0: return None # No dividends yet
        
        yield_pct = (ttm_divs / price) * 100
        
        # 5-Year Growth
        five_years_ago_end = one_year_ago - datetime.timedelta(days=365*4)
        five_years_ago_start = five_years_ago_end - datetime.timedelta(days=365)
        mask_5y = (hist.index >= pd.Timestamp(five_years_ago_start.date())) & \
                  (hist.index < pd.Timestamp(five_years_ago_end.date()))
        divs_5y_ago = hist.loc[mask_5y, 'dividends'].sum()
        
        dgr_pct = 0
        if divs_5y_ago > 0:
            total_growth = ttm_divs / divs_5y_ago
            dgr = (total_growth ** (1/5)) - 1
            dgr_pct = dgr * 100
        else:
            # If we don't have 5y history but have current dividends, 
            # we can assume a default growth or just use Yield.
            # Let's be conservative: assume 0 growth if undefined.
            pass
            
        return yield_pct + dgr_pct

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        stock_data = self.latest_stocks_info[self.ticker]
        today_price = extract_close_price(stock_data, self.today_time)
        if today_price is None or np.isnan(today_price): return choices

        shares = self.hold_stock_number.get(self.ticker, 0)
        cash = self.initial_money + self.changed_money
        total_equity = cash + (shares * today_price)
        if total_equity <= 0: return choices

        # Cooldown / Stop Loss
        if self.cooldown_counter > 0:
            self.cooldown_counter -= 1
            if shares > 0:
                 choices.append({self.ticker: (buy_or_sell_choice.Sell, shares)})
            return choices
            
        if shares > 0:
            self.max_price = max(self.max_price, today_price)
            if today_price < self.max_price * (1 - self.stop_loss_pct):
                choices.append({self.ticker: (buy_or_sell_choice.Sell, shares)})
                self.max_price = 0
                self.cooldown_counter = 10
                return choices

        # Calculations
        hist = stock_data.get_history_price(self.today_time)
        closes = hist["close"].values
        if len(closes) < max(self.hurst_window, self.regime_ma) + 10: return choices

        # 1. Macro Ceiling
        macro_ceil = self._get_macro_ceiling()
        
        # 2. Fundamental Base (Chowder)
        fund_score = self._get_fundamental_score(hist, today_price)
        
        base_alloc = 0.0
        if fund_score is not None:
            if fund_score > self.buy_score: base_alloc = 0.5 # High Quality -> Hold 50%
            elif fund_score < self.sell_score: base_alloc = 0.0 # Deteriorating -> 0%
            else: base_alloc = 0.3 # Neutral/Hold
        else:
            # Pre-2012 AAPL (No Dividends): Rely purely on Technicals
            # Treat as "Neutral" or "Growth phase"
            base_alloc = 0.0 # No free pass, earn it via trend
            
        # 3. Technical Boost (V3 Logic)
        returns = pd.Series(closes).pct_change().dropna()
        if len(returns) < 20: return choices
        realized_vol = returns.tail(20).std() * np.sqrt(252)
        if realized_vol == 0: realized_vol = 0.01
        
        vol_scalar = self.target_vol / realized_vol
        vol_scalar = min(vol_scalar, 1.0)
        
        ema_regime = pd.Series(closes).ewm(span=self.regime_ma, adjust=False).mean().iloc[-1]
        is_bull_regime = today_price > ema_regime
        
        H, _ = math_util.rs_analysis_scientific(closes[-self.hurst_window:])
        is_trending = H > self.hurst_threshold
        
        tech_alloc = 0.0
        if is_bull_regime:
            if is_trending:
                tech_alloc = 1.0 * vol_scalar
            else:
                tech_alloc = 0.7 * vol_scalar
        else:
            # Bear Regime
            if H > 0.65: # Contrarian
                 tech_alloc = 0.3 * vol_scalar
            else:
                 tech_alloc = 0.0
        
        # === Final Synthesis ===
        # We combine Base (Fund) and Tech. 
        # Logic: If Tech is Bullish, we go Tech Alloc (usually high).
        # If Tech is Bearish, we fall back to Base Alloc (Fundamental Hold), 
        # UNLESS Macro Ceiling forces us down.
        
        # Actually, let's take the MAX of Base and Tech, then clamp by Macro.
        # This means: Even if Trend is bad, if Fundamentals are screaming buy (Score > 12), we hold some.
        # BUT: If Trend is bad (Price < EMA 100), holding against the trend is dangerous.
        # So maybe: Tech Alloc is the multiplier, Fundamental is the conviction?
        
        # Refined Logic:
        # Tech Alloc is the primary driver (0.0 to 1.0).
        # If Fundamental is Great (>12), we boost Tech Alloc or ignore minor volatility.
        # If Fundamental is Bad (<8), we cap Tech Alloc.
        
        raw_alloc = tech_alloc
        
        if fund_score is not None:
            if fund_score > self.buy_score:
                # Great fundamentals: Allow higher vol, maybe floor allocation?
                raw_alloc = max(raw_alloc, 0.2) # Always hold 20% if super cheap
            elif fund_score < self.sell_score:
                # Bad fundamentals: Cap allocation
                raw_alloc = min(raw_alloc, 0.5)
        
        # Apply Macro Ceiling
        final_alloc = min(raw_alloc, macro_ceil)
        
        # Execution
        target_value = total_equity * final_alloc
        current_value = shares * today_price
        diff_value = target_value - current_value
        
        if abs(diff_value) > total_equity * 0.05 or (shares == 0 and final_alloc > 0) or (final_alloc == 0 and shares > 0):
            if diff_value > 0:
                num = diff_value / today_price
                choices.append({self.ticker: (buy_or_sell_choice.Buy, num)})
                if shares == 0: self.max_price = today_price
            elif diff_value < 0:
                num = abs(diff_value) / today_price
                choices.append({self.ticker: (buy_or_sell_choice.Sell, num)})
                
        return choices
