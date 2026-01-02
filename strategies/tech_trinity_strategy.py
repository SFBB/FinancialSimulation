from utility.strategy import strategy_base, buy_or_sell_choice
from utility.stock_util import extract_close_price
from utility.math_util import math_util
import numpy as np
import pandas as pd
import datetime

class Tech_Trinity_Strategy(strategy_base):
    """
    Tech Trinity Portfolio Strategy V2 (Adaptive Momentum)
    -----------------------------------------------------
    Improvements to beat the market:
    1. Dynamic Momentum: Only invest in top N assets by recent performance.
    2. Adaptive Weights: Instead of static 1/N, focus on the 'Winners'.
    3. Relaxed Filters: Lower Hurst (0.52) to stay in trends longer.
    """

    def __init__(
        self,
        tickers=["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "KO"],
        initial_money=1000000,
        # Ranking Params
        top_k=4,            
        momentum_window=120, 
        # Signal Params
        hurst_threshold=0.52,
        hurst_window=100,    # Added to signature
        regime_ma=100,
        target_vol=0.40,     
        macro_ma=50,
        stop_loss_pct=0.12   
    ):
        super().__init__()
        self.stock_names = tickers
        self.initial_money = initial_money
        
        self.top_k = top_k
        self.momentum_window = momentum_window
        self.hurst_threshold = hurst_threshold
        self.hurst_window = hurst_window
        self.regime_ma = regime_ma
        self.target_vol = target_vol
        self.macro_ma = macro_ma
        self.stop_loss_pct = stop_loss_pct
        
        self.states = {t: {'max_price': 0, 'cooldown': 0} for t in tickers}

    def get_name(self):
        return f"Momentum_Super_Portfolio_Top{self.top_k}of{len(self.stock_names)}"

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
        
        if risk_level >= 2: return 0.6
        if risk_level == 1: return 0.9
        return 1.0

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        
        # 1. Total Equity Calc
        total_equity = self.initial_money + self.changed_money
        for t in self.stock_names:
            if t in self.latest_stocks_info:
                p = extract_close_price(self.latest_stocks_info[t], self.today_time)
                if p: total_equity += self.hold_stock_number.get(t, 0) * p
        
        if total_equity <= 0: return []
        
        # 2. Momentum Ranking
        scores = {}
        for t in self.stock_names:
            stock_data = self.latest_stocks_info.get(t)
            if not stock_data: continue
            hist = stock_data.get_history_price(self.today_time)
            if len(hist) < self.momentum_window: continue
            
            prices = hist['close'].values
            ret = (prices[-1] - prices[-self.momentum_window]) / prices[-self.momentum_window]
            scores[t] = ret
            
        sorted_tickers = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_tickers = [t[0] for t in sorted_tickers[:self.top_k]]
        
        slot_equity = total_equity / self.top_k
        macro_ceil = self._get_macro_ceiling()

        # 3. Execution for Winners and Losers
        for ticker in self.stock_names:
            stock_data = self.latest_stocks_info.get(ticker)
            if not stock_data: continue
            
            today_price = extract_close_price(stock_data, self.today_time)
            if today_price is None or np.isnan(today_price): continue
            
            shares = self.hold_stock_number.get(ticker, 0)
            current_slot_value = shares * today_price
            state = self.states[ticker]
            
            # EXIT LOSERS
            if ticker not in top_tickers:
                if shares > 0:
                    choices.append({ticker: (buy_or_sell_choice.Sell, shares)})
                    state['max_price'] = 0
                continue

            # MANAGE WINNERS
            hist = stock_data.get_history_price(self.today_time)
            closes = hist["close"].values
            if len(closes) < max(self.hurst_window, self.regime_ma) + 10: continue

            returns = pd.Series(closes).pct_change().dropna()
            if len(returns) < 20: continue
            realized_vol = returns.tail(20).std() * np.sqrt(252)
            vol_scalar = min(self.target_vol / realized_vol, 1.0)
            
            ema_regime = pd.Series(closes).ewm(span=self.regime_ma, adjust=False).mean().iloc[-1]
            is_bull_regime = today_price > ema_regime
            
            H, _ = math_util.rs_analysis_scientific(closes[-self.hurst_window:])
            is_trending = H > self.hurst_threshold
            
            final_alloc_pct = 0.0
            if is_bull_regime:
                if is_trending: final_alloc_pct = 1.0 * vol_scalar
                else: final_alloc_pct = 0.7 * vol_scalar
            else:
                if H > 0.65: final_alloc_pct = 0.3 * vol_scalar
            
            final_alloc_pct = min(final_alloc_pct, macro_ceil)
            
            # REBALANCE
            target_value = slot_equity * final_alloc_pct
            diff_value = target_value - current_slot_value
            
            if abs(diff_value) > slot_equity * 0.05 or (shares == 0 and final_alloc_pct > 0) or (final_alloc_pct == 0 and shares > 0):
                if diff_value > 0:
                    num = diff_value / today_price
                    choices.append({ticker: (buy_or_sell_choice.Buy, num)})
                    if shares == 0: state['max_price'] = today_price
                elif diff_value < 0:
                    num = abs(diff_value) / today_price
                    choices.append({ticker: (buy_or_sell_choice.Sell, num)})

        return choices
