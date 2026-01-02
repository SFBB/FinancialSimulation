from utility.strategy import strategy_base, buy_or_sell_choice
from utility.stock_util import extract_close_price
import numpy as np
import pandas as pd
import datetime

class AAPL_Dividend_Growth_Strategy(strategy_base):
    """
    AAPL Dividend Growth Strategy (Chowder Rule Style)
    --------------------------------------------------
    Instead of absolute Yield, we look at Yield + Dividend Growth (Total Return Potential).
    Suitable for Growth stocks like AAPL that pay small but fast-growing dividends.
    
    Metric: Chowder Score = Current Yield (%) + 5-Year Dividend CAGR (%)
    
    Logic:
    1. Calculate 5-Year Dividend Growth Rate (DGR).
    2. Calculate Current TTM Yield.
    3. Chowder Score = Yield + DGR.
    4. Buy if Score > 12 (High growth potential).
    5. Sell if Score < 8 (Overvalued or Growth Slowing).
    6. Trend Filter: Price > EMA 100.
    """

    def __init__(
        self,
        ticker="AAPL",
        initial_money=1000000,
        buy_score=12.0,   # Yield + DGR > 12
        sell_score=8.0,   # Yield + DGR < 8
        trend_ma=100,
        stop_loss_pct=0.10
    ):
        super().__init__()
        self.stock_names = [ticker]
        self.ticker = ticker
        self.initial_money = initial_money
        
        self.buy_score = buy_score
        self.sell_score = sell_score
        self.trend_ma = trend_ma
        self.stop_loss_pct = stop_loss_pct
        
        self.max_price = 0

    def get_name(self):
        return f"AAPL_DivGrowth(Score_Buy{self.buy_score}_Sell{self.sell_score})"

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
        # Need 5 years history for CAGR
        if len(hist) < 365 * 5: return choices
        
        chowder_score = 0.0
        current_yield_pct = 0.0
        dgr_pct = 0.0
        
        if 'dividends' in hist.columns:
            # 1. Current TTM Dividends
            one_year_ago = self.today_time - datetime.timedelta(days=365)
            mask_ttm = hist.index >= pd.Timestamp(one_year_ago.date())
            ttm_divs = hist.loc[mask_ttm, 'dividends'].sum()
            
            if ttm_divs > 0:
                current_yield_pct = (ttm_divs / today_price) * 100
                
                # 2. 5-Year CAGR
                # Divs 5 years ago
                five_years_ago_end = one_year_ago - datetime.timedelta(days=365*4)
                five_years_ago_start = five_years_ago_end - datetime.timedelta(days=365)
                
                mask_5y = (hist.index >= pd.Timestamp(five_years_ago_start.date())) & (hist.index < pd.Timestamp(five_years_ago_end.date()))
                
                divs_5y_ago = hist.loc[mask_5y, 'dividends'].sum()
                
                if divs_5y_ago > 0:
                    # CAGR formula: (End / Start)^(1/n) - 1
                    # Here we compare TTM vs TTM-5y
                    total_growth = ttm_divs / divs_5y_ago
                    dgr = (total_growth ** (1/5)) - 1
                    dgr_pct = dgr * 100
                    
                    chowder_score = current_yield_pct + dgr_pct

        # Trend
        ema_trend = hist['close'].ewm(span=self.trend_ma, adjust=False).mean().iloc[-1]
        is_uptrend = today_price > ema_trend
        
        # Debug (Jan 1st)
        if self.today_time.day == 1 and self.today_time.month == 1:
             print(f"Date: {self.today_time.date()} | Yield: {current_yield_pct:.2f}% | DGR(5y): {dgr_pct:.2f}% | Score: {chowder_score:.2f}")

        action = "HOLD"
        
        # === SELL ===
        if shares > 0:
            self.max_price = max(self.max_price, today_price)
            if today_price < self.max_price * (1 - self.stop_loss_pct):
                action = "SELL"
            # Sell if Score drops (Growth slows or Price too high dropping yield)
            elif chowder_score < self.sell_score and chowder_score > 0:
                action = "SELL"
        
        # === BUY ===
        if action != "SELL":
            # Buy High Total Return Potential
            if chowder_score > self.buy_score and is_uptrend:
                action = "BUY"
                
        # === EXECUTE ===
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
