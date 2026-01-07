from utility.strategy import strategy_base, buy_or_sell_choice, MarketConfig
from utility.stock_util import extract_close_price
from utility.math_util import math_util
import numpy as np
import pandas as pd
import datetime

class AShare_Dragon_Strategy(strategy_base):
    """
    A-Share Hidden Dragon Strategy V2 (Momentum Top K)
    --------------------------------------------------
    Target: China Core Assets.
    Logic:
    1. Macro Filter (CNY): If RMB depreciates fast (>2% above MA20), reduce exposure.
    2. Momentum Ranking: Invest only in Top K assets (Leader Effect).
    3. Trend (Hurst): Only enter if Trend Persistence (H > 0.55).
    4. Volume Sniper: Enter on Volume Breakouts.
    """

    def __init__(
        self,
        tickers=["600519.SS", "601318.SS", "000858.SZ", "002594.SZ", "600030.SS"],
        initial_money=1000000,
        # Ranking
        top_k=2,
        momentum_window=120,
        # Vol Sniper Params
        vol_window=20,
        calm_threshold=0.4, 
        spike_multiplier=1.5,
        # Trend Params
        hurst_threshold=0.55,
        hurst_window=100,
        trend_ma=60,
        # Risk
        stop_loss_pct=0.08
    ):
        super().__init__(market_config=MarketConfig.CN_Market())
        self.stock_names = tickers
        self.initial_money = initial_money
        
        self.top_k = top_k
        self.momentum_window = momentum_window
        self.vol_window = vol_window
        self.calm_threshold = calm_threshold
        self.spike_multiplier = spike_multiplier
        self.hurst_threshold = hurst_threshold
        self.hurst_window = hurst_window
        self.trend_ma = trend_ma
        self.stop_loss_pct = stop_loss_pct
        
        self.states = {t: {'max_price': 0, 'state': 'WAIT'} for t in tickers}

    def get_name(self):
        return f"AShare_Dragon_Top{self.top_k}of{len(self.stock_names)}"

    def get_stock_source(self, stock_name):
        return "yahoo"

    def get_benchmark_ticker(self):
        return "000300.SS"

    def _get_macro_ceiling(self):
        cny_info = self.latest_economics_info.get('cny')
        if cny_info:
            hist = cny_info.get_history_info(self.today_time, datetime.timedelta(days=60))
            if hist is not None and not hist.empty:
                col = 'Close' if 'Close' in hist.columns else 'close'
                if col in hist.columns:
                    prices = hist[col]
                    if len(prices) > 20:
                        ma20 = prices.rolling(window=20).mean().iloc[-1]
                        curr = prices.iloc[-1]
                        if curr > ma20 * 1.02:
                            return 0.5 # Defensive
        return 1.0 

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        
        total_equity = self.initial_money + self.changed_money
        for t in self.stock_names:
            if t in self.latest_stocks_info:
                p = extract_close_price(self.latest_stocks_info[t], self.today_time)
                if p: total_equity += self.hold_stock_number.get(t, 0) * p
        
        if total_equity <= 0: return []
        
        # Rank Assets
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

        for ticker in self.stock_names:
            stock_data = self.latest_stocks_info.get(ticker)
            if not stock_data: continue
            today_price = extract_close_price(stock_data, self.today_time)
            if today_price is None or np.isnan(today_price): continue
            
            shares = self.hold_stock_number.get(ticker, 0)
            frozen = self.frozen_stock.get(ticker, 0)
            sellable = shares - frozen
            state = self.states[ticker]
            
            # --- Exit Losers ---
            if ticker not in top_tickers:
                if sellable > 0:
                    choices.append({ticker: (buy_or_sell_choice.Sell, sellable)})
                    state['max_price'] = 0
                continue

            # --- Manage Winners ---
            if sellable > 0:
                state['max_price'] = max(state['max_price'], today_price)
                if today_price < state['max_price'] * (1 - self.stop_loss_pct):
                    choices.append({ticker: (buy_or_sell_choice.Sell, sellable)})
                    state['max_price'] = 0
                    continue
            
            hist = stock_data.get_history_price(self.today_time)
            closes = hist['close']
            volumes = hist['volume']
            
            if len(closes) < max(self.vol_window, self.hurst_window) + 5: continue
            
            # Trend Check
            ema_trend = closes.ewm(span=self.trend_ma, adjust=False).mean().iloc[-1]
            H, _ = math_util.rs_analysis_scientific(closes.values[-self.hurst_window:])
            is_uptrend = (today_price > ema_trend) and (H > self.hurst_threshold)
            
            # Volume Check
            vol_mean = volumes.rolling(window=self.vol_window).mean().iloc[-1]
            vol_std = volumes.rolling(window=self.vol_window).std().iloc[-1]
            if vol_mean == 0: continue
            vol_cv = vol_std / vol_mean
            current_vol = volumes.iloc[-1]
            is_price_up = closes.iloc[-1] > closes.iloc[-2]
            
            action = "HOLD"
            
            if shares == 0:
                if vol_cv < self.calm_threshold:
                    state['state'] = "READY"
                
                prev_cv = (volumes.rolling(window=self.vol_window).std() / volumes.rolling(window=self.vol_window).mean()).iloc[-2]
                
                if prev_cv < self.calm_threshold:
                    if current_vol > vol_mean * self.spike_multiplier and is_price_up:
                        if is_uptrend:
                            action = "BUY"
            
            elif sellable > 0:
                if today_price < ema_trend:
                    action = "SELL"
            
            # --- Allocation ---
            target_alloc_pct = 0.0
            if action == "BUY": target_alloc_pct = 1.0
            elif action == "HOLD" and shares > 0: target_alloc_pct = 1.0
            elif action == "SELL": target_alloc_pct = 0.0
            
            final_alloc_pct = min(target_alloc_pct, macro_ceil)
            
            target_value = slot_equity * final_alloc_pct
            current_value = shares * today_price
            diff_value = target_value - current_value
            
            if abs(diff_value) > slot_equity * 0.1 or action == "BUY" or action == "SELL":
                if diff_value > 0:
                    num = diff_value / today_price
                    num = int(num / 100) * 100
                    if num > 0:
                        choices.append({ticker: (buy_or_sell_choice.Buy, num)})
                        if shares == 0: state['max_price'] = today_price
                elif diff_value < 0:
                    num = abs(diff_value) / today_price
                    num = int(num / 100) * 100
                    num = min(num, sellable)
                    if num > 0:
                        choices.append({ticker: (buy_or_sell_choice.Sell, num)})

        return choices