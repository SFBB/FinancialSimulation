from utility.strategy import strategy_base, buy_or_sell_choice
from utility.stock_util import extract_close_price
from utility.math_util import math_util
import numpy as np
import pandas as pd
import datetime

class Tech_Trinity_Static_Strategy(strategy_base):
    """
    Tech Trinity Portfolio V1 (Static 1/N Defensive)
    ------------------------------------------------
    The "Classic" version.
    
    1. Allocation: Static 1/N split among all assets.
    2. Logic: Hybrid of Fundamental (Chowder) and Technical (FMH).
       - Good Fundamentals (Score > 12) provide a allocation floor (0.2).
       - Bad Fundamentals (Score < 8) provide a allocation cap (0.5).
    3. Macro: Global risk ceiling.
    
    Pros: Extremely low drawdown, very stable.
    Cons: Carries underperformers (like KO) in bull markets.
    """

    def __init__(
        self,
        tickers=["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "KO"],
        initial_money=1000000,
        # Fundamental Params
        buy_score=12.0,
        sell_score=8.0,
        # Technical Params
        hurst_threshold=0.55, # Conservative
        hurst_window=100,
        regime_ma=100,
        target_vol=0.35,
        macro_ma=50,
        stop_loss_pct=0.10
    ):
        super().__init__()
        self.stock_names = tickers
        self.initial_money = initial_money
        
        self.buy_score = buy_score
        self.sell_score = sell_score
        self.hurst_threshold = hurst_threshold
        self.hurst_window = hurst_window
        self.regime_ma = regime_ma
        self.target_vol = target_vol
        self.macro_ma = macro_ma
        self.stop_loss_pct = stop_loss_pct
        
        # State tracking
        self.states = {t: {'max_price': 0, 'cooldown': 0} for t in tickers}

    def get_name(self):
        return f"Portfolio_V1_Static_N{len(self.stock_names)}"

    def get_stock_source(self, stock_name):
        return "yahoo"

    def _get_macro_ceiling(self):
        risk_level = 0
        for name in ['oil', 'us_debt']:
            info = self.latest_economics_info.get(name)
            if info:
                hist = info.get_history_info(self.today_time, datetime.timedelta(days=self.macro_ma * 2 + 30))
                if hist is not None and not hist.empty:
                    col = 'Close' if 'Close' in hist.columns else 'close'
                    if col in hist.columns:
                        prices = hist[col]
                        if len(prices) > self.macro_ma:
                            sma = prices.rolling(window=self.macro_ma).mean().iloc[-1]
                            curr = prices.iloc[-1]
                            if curr > sma * 1.05: risk_level += 1
        
        if risk_level >= 2: return 0.5
        if risk_level == 1: return 0.8
        return 1.0

    def _get_fundamental_score(self, hist, price):
        if 'dividends' not in hist.columns: return None
        one_year_ago = self.today_time - datetime.timedelta(days=365)
        mask_ttm = hist.index >= pd.Timestamp(one_year_ago.date())
        ttm_divs = hist.loc[mask_ttm, 'dividends'].sum()
        
        if ttm_divs == 0: return None
        
        yield_pct = (ttm_divs / price) * 100
        
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
            
        return yield_pct + dgr_pct

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        
        total_equity = self.initial_money + self.changed_money
        for t in self.stock_names:
            if t in self.latest_stocks_info:
                p = extract_close_price(self.latest_stocks_info[t], self.today_time)
                if p: total_equity += self.hold_stock_number.get(t, 0) * p
        
        if total_equity <= 0: return []
        
        # V1: Static 1/N Allocation
        slot_equity = total_equity / len(self.stock_names)
        macro_ceil = self._get_macro_ceiling()

        for ticker in self.stock_names:
            stock_data = self.latest_stocks_info.get(ticker)
            if not stock_data: continue
            today_price = extract_close_price(stock_data, self.today_time)
            if today_price is None or np.isnan(today_price): continue
            
            shares = self.hold_stock_number.get(ticker, 0)
            current_slot_value = shares * today_price
            state = self.states[ticker]
            
            # Risk Management
            if state['cooldown'] > 0:
                state['cooldown'] -= 1
                if shares > 0: choices.append({ticker: (buy_or_sell_choice.Sell, shares)})
                continue
            
            if shares > 0:
                state['max_price'] = max(state['max_price'], today_price)
                if today_price < state['max_price'] * (1 - self.stop_loss_pct):
                    choices.append({ticker: (buy_or_sell_choice.Sell, shares)})
                    state['max_price'] = 0
                    state['cooldown'] = 10
                    continue

            # Signal
            hist = stock_data.get_history_price(self.today_time)
            closes = hist["close"].values
            if len(closes) < max(self.hurst_window, self.regime_ma) + 10: continue

            # Fundamental
            fund_score = self._get_fundamental_score(hist, today_price)
            
            # Technical
            returns = pd.Series(closes).pct_change().dropna()
            if len(returns) < 20: continue
            realized_vol = returns.tail(20).std() * np.sqrt(252)
            if realized_vol == 0: realized_vol = 0.01
            vol_scalar = min(self.target_vol / realized_vol, 1.0)
            
            ema_regime = pd.Series(closes).ewm(span=self.regime_ma, adjust=False).mean().iloc[-1]
            is_bull_regime = today_price > ema_regime
            
            H, _ = math_util.rs_analysis_scientific(closes[-self.hurst_window:])
            is_trending = H > self.hurst_threshold
            
            # Base Allocation Logic
            tech_alloc = 0.0
            if is_bull_regime:
                if is_trending: tech_alloc = 1.0 * vol_scalar
                else: tech_alloc = 0.7 * vol_scalar
            else:
                if H > 0.65: tech_alloc = 0.3 * vol_scalar
                else: tech_alloc = 0.0
            
            # Merge Fundamental
            final_alloc = tech_alloc
            if fund_score is not None:
                if fund_score > self.buy_score: final_alloc = max(final_alloc, 0.2)
                elif fund_score < self.sell_score: final_alloc = min(final_alloc, 0.5)
            
            # Apply Macro
            final_alloc = min(final_alloc, macro_ceil)
            
            # Execute
            target_value = slot_equity * final_alloc
            diff_value = target_value - current_slot_value
            
            if abs(diff_value) > slot_equity * 0.05 or (shares == 0 and final_alloc > 0) or (final_alloc == 0 and shares > 0):
                if diff_value > 0:
                    num = diff_value / today_price
                    choices.append({ticker: (buy_or_sell_choice.Buy, num)})
                    if shares == 0: state['max_price'] = today_price
                elif diff_value < 0:
                    num = abs(diff_value) / today_price
                    choices.append({ticker: (buy_or_sell_choice.Sell, num)})

        return choices
