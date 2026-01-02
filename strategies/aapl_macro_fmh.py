from utility.strategy import strategy_base, buy_or_sell_choice
from utility.stock_util import extract_close_price
from utility.math_util import math_util
import numpy as np
import pandas as pd
import datetime

class AAPL_Macro_FMH_Strategy(strategy_base):
    """
    AAPL Strategy based on Fractal Market Hypothesis (Hurst Exponent) 
    filtered by Macroeconomic Indicators (Oil & US Debt Yields).
    """

    def __init__(
        self,
        ticker="AAPL",
        initial_money=1000000,
        hurst_threshold=0.55,
        hurst_window=100,
        trend_ma=50,
        macro_ma=50,
        stop_loss_pct=0.08
    ):
        super().__init__()
        self.stock_names = [ticker]
        self.ticker = ticker
        self.initial_money = initial_money
        
        self.hurst_threshold = hurst_threshold
        self.hurst_window = hurst_window
        self.trend_ma = trend_ma
        self.macro_ma = macro_ma
        self.stop_loss_pct = stop_loss_pct
        
        self.max_price = 0
        self.cooldown_counter = 0

    def get_name(self):
        return f"AAPL_Macro_FMH(H>{self.hurst_threshold}_MacroCheck)"

    def get_stock_source(self, stock_name):
        return "yahoo"

    def _get_macro_risk(self):
        """
        Returns risk level: 0 (Low), 1 (Medium), 2 (High)
        """
        risk_score = 0
        
        # Check Oil (CL=F)
        oil_info = self.latest_economics_info.get('oil')
        if oil_info:
            # Get history (enough for MA)
            oil_hist = oil_info.get_history_info(self.today_time, datetime.timedelta(days=self.macro_ma * 2 + 30))
            if oil_hist is not None and not oil_hist.empty:
                # Yahoo Finance usually returns 'Close' or 'close'
                if 'Close' in oil_hist.columns:
                     prices = oil_hist['Close']
                elif 'close' in oil_hist.columns:
                     prices = oil_hist['close']
                else:
                     prices = None
                
                if prices is not None and len(prices) > self.macro_ma:
                    sma = prices.rolling(window=self.macro_ma).mean().iloc[-1]
                    curr = prices.iloc[-1]
                    # If Oil is trending up significantly (> 5% above SMA50), it's inflationary/risk-off
                    if curr > sma * 1.05:
                        risk_score += 1

        # Check US Debt (^TNX)
        debt_info = self.latest_economics_info.get('us_debt')
        if debt_info:
            debt_hist = debt_info.get_history_info(self.today_time, datetime.timedelta(days=self.macro_ma * 2 + 30))
            if debt_hist is not None and not debt_hist.empty:
                if 'Close' in debt_hist.columns:
                     prices = debt_hist['Close']
                elif 'close' in debt_hist.columns:
                     prices = debt_hist['close']
                else:
                     prices = None

                if prices is not None and len(prices) > self.macro_ma:
                    sma = prices.rolling(window=self.macro_ma).mean().iloc[-1]
                    curr = prices.iloc[-1]
                    # If Yields are spiking (> 5% above SMA50), it hurts tech valuations
                    if curr > sma * 1.05:
                        risk_score += 1
                        
        return risk_score

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        stock_data = self.latest_stocks_info[self.ticker]
        today_price = extract_close_price(stock_data, self.today_time)

        if today_price is None or np.isnan(today_price):
            return choices

        # 1. Asset Status
        shares = self.hold_stock_number.get(self.ticker, 0)
        cash = self.initial_money + self.changed_money
        total_equity = cash + (shares * today_price)

        if total_equity <= 0:
            return choices

        # 2. Risk Management
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
                self.cooldown_counter = 5
                return choices

        # 3. Calculations
        hist = stock_data.get_history_price(self.today_time)
        closes = hist["close"].values
        
        if len(closes) < self.hurst_window + 10:
            return choices

        # Hurst Exponent
        H, _ = math_util.rs_analysis_scientific(closes[-self.hurst_window:])
        
        # Trend
        sma = np.mean(closes[-self.trend_ma:])
        is_uptrend = today_price > sma
        
        # Macro Risk
        macro_risk = self._get_macro_risk()
        
        # 4. Decision Logic
        target_pct = 0.0
        
        # Condition: Strong Fractal Trend + Price Trend
        if H > self.hurst_threshold and is_uptrend:
            if macro_risk == 0:
                target_pct = 1.0 # Full Bull
            elif macro_risk == 1:
                target_pct = 0.5 # Cautious Bull
            else:
                target_pct = 0.0 # Macro Headwinds override FMH
        else:
            target_pct = 0.0
            self.max_price = 0
            
        # 5. Execution
        target_value = total_equity * target_pct
        current_value = shares * today_price
        diff_value = target_value - current_value
        
        # Trade buffer to avoid small rebalancing
        trade_threshold = total_equity * 0.10
        
        is_critical_trade = (shares == 0 and target_pct > 0) or (target_pct == 0 and shares > 0)
        
        if abs(diff_value) > trade_threshold or is_critical_trade:
            if diff_value > 0:
                num = diff_value / today_price
                choices.append({self.ticker: (buy_or_sell_choice.Buy, num)})
                if shares == 0: self.max_price = today_price
            elif diff_value < 0:
                num = abs(diff_value) / today_price
                choices.append({self.ticker: (buy_or_sell_choice.Sell, num)})
                
        return choices


class AAPL_Macro_FMH_Strategy_V2(strategy_base):
    """
    AAPL Strategy V2:
    - Long Term Trend Filter (EMA 120) for Regime Detection.
    - Volatility Targeting (Target Vol 20%).
    - FMH Hurst Filter for Trend Strength.
    - Macro Filter (Oil/Yields) for Risk Adjustment.
    """

    def __init__(
        self,
        ticker="AAPL",
        initial_money=1000000,
        hurst_threshold=0.55,
        hurst_window=100,
        regime_ma=120, # EMA 120 for Bull/Bear regime
        target_vol=0.20, # 20% Annualized Volatility Target
        macro_ma=50,
        stop_loss_pct=0.10
    ):
        super().__init__()
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
        return f"AAPL_Macro_FMH_V2(VolTarget{self.target_vol}_Regime{self.regime_ma})"

    def get_stock_source(self, stock_name):
        return "yahoo"

    def _get_macro_risk(self):
        """
        Returns risk multiplier: 1.0 (Safe) or 0.5 (Risk Off) or 0.0 (Extreme Risk)
        """
        risk_level = 0
        
        # Check Oil
        oil_info = self.latest_economics_info.get('oil')
        if oil_info:
            oil_hist = oil_info.get_history_info(self.today_time, datetime.timedelta(days=self.macro_ma * 2 + 30))
            if oil_hist is not None and not oil_hist.empty:
                prices = None
                if 'Close' in oil_hist.columns: prices = oil_hist['Close']
                elif 'close' in oil_hist.columns: prices = oil_hist['close']
                
                if prices is not None and len(prices) > self.macro_ma:
                    sma = prices.rolling(window=self.macro_ma).mean().iloc[-1]
                    curr = prices.iloc[-1]
                    if curr > sma * 1.05: risk_level += 1

        # Check Debt
        debt_info = self.latest_economics_info.get('us_debt')
        if debt_info:
            debt_hist = debt_info.get_history_info(self.today_time, datetime.timedelta(days=self.macro_ma * 2 + 30))
            if debt_hist is not None and not debt_hist.empty:
                prices = None
                if 'Close' in debt_hist.columns: prices = debt_hist['Close']
                elif 'close' in debt_hist.columns: prices = debt_hist['close']
                
                if prices is not None and len(prices) > self.macro_ma:
                    sma = prices.rolling(window=self.macro_ma).mean().iloc[-1]
                    curr = prices.iloc[-1]
                    if curr > sma * 1.05: risk_level += 1
        
        if risk_level >= 2: return 0.0 # Both Oil and Yields spiking -> Stay Cash
        if risk_level == 1: return 0.5 # Half Risk
        return 1.0 # Full Risk

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        stock_data = self.latest_stocks_info[self.ticker]
        today_price = extract_close_price(stock_data, self.today_time)

        if today_price is None or np.isnan(today_price):
            return choices

        # 1. Asset Status
        shares = self.hold_stock_number.get(self.ticker, 0)
        cash = self.initial_money + self.changed_money
        total_equity = cash + (shares * today_price)

        if total_equity <= 0:
            return choices

        # 2. Risk Management
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
                self.cooldown_counter = 10 # Longer cooldown for V2
                return choices

        # 3. Calculations
        hist = stock_data.get_history_price(self.today_time)
        closes = hist["close"].values
        
        if len(closes) < max(self.hurst_window, self.regime_ma) + 10:
            return choices

        # A. Volatility Calculation (20-day rolling)
        returns = pd.Series(closes).pct_change().dropna()
        if len(returns) < 20: return choices
        realized_vol = returns.tail(20).std() * np.sqrt(252)
        if realized_vol == 0: realized_vol = 0.01 # Avoid div by zero
        
        # Volatility Scalar
        vol_scalar = self.target_vol / realized_vol
        vol_scalar = min(vol_scalar, 1.0) # Cap at 1.0 (No Leverage)

        # B. Regime Filter (EMA 120)
        ema_regime = pd.Series(closes).ewm(span=self.regime_ma, adjust=False).mean().iloc[-1]
        is_bull_regime = today_price > ema_regime
        
        # C. Hurst Trend
        H, _ = math_util.rs_analysis_scientific(closes[-self.hurst_window:])
        is_trending = H > self.hurst_threshold
        
        # D. Macro Multiplier
        macro_mult = self._get_macro_risk()
        
        # 4. Decision Logic
        target_pct = 0.0
        
        if is_bull_regime:
            if is_trending:
                # Strong Bull + Trend -> Target Vol allocation * Macro Adjust
                target_pct = 1.0 * vol_scalar * macro_mult
            else:
                # Bull Regime but Chop -> Reduced exposure
                target_pct = 0.5 * vol_scalar * macro_mult
        else:
            # Bear Regime -> Cash
            target_pct = 0.0
            self.max_price = 0
            
        # 5. Execution
        target_value = total_equity * target_pct
        current_value = shares * today_price
        diff_value = target_value - current_value
        
        trade_threshold = total_equity * 0.05 # Tighter threshold for Vol Targeting rebalancing
        
        is_critical_trade = (shares == 0 and target_pct > 0) or (target_pct == 0 and shares > 0)
        
        if abs(diff_value) > trade_threshold or is_critical_trade:
            if diff_value > 0:
                num = diff_value / today_price
                choices.append({self.ticker: (buy_or_sell_choice.Buy, num)})
                if shares == 0: self.max_price = today_price
            elif diff_value < 0:
                num = abs(diff_value) / today_price
                choices.append({self.ticker: (buy_or_sell_choice.Sell, num)})
                
        return choices

class AAPL_Macro_FMH_Strategy_V3(strategy_base):
    """
    AAPL Strategy V3:
    - Higher Volatility Target (35%) to capture more upside.
    - Softer Macro Risk (Don't exit fully, just reduce).
    - Faster Regime Filter (EMA 100).
    """

    def __init__(
        self,
        ticker="AAPL",
        initial_money=1000000,
        hurst_threshold=0.55,
        hurst_window=100,
        regime_ma=100, # Faster than 120
        target_vol=0.35, # 35% Vol Target (Aggressive)
        macro_ma=50,
        stop_loss_pct=0.10
    ):
        super().__init__()
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
        return f"AAPL_Macro_FMH_V3(VolTarget{self.target_vol})"

    def get_stock_source(self, stock_name):
        return "yahoo"

    def _get_macro_risk(self):
        """
        V3 Macro: Less binary. 
        """
        risk_level = 0
        
        oil_info = self.latest_economics_info.get('oil')
        if oil_info:
            oil_hist = oil_info.get_history_info(self.today_time, datetime.timedelta(days=self.macro_ma * 2 + 30))
            if oil_hist is not None and not oil_hist.empty:
                prices = None
                if 'Close' in oil_hist.columns: prices = oil_hist['Close']
                elif 'close' in oil_hist.columns: prices = oil_hist['close']
                
                if prices is not None and len(prices) > self.macro_ma:
                    sma = prices.rolling(window=self.macro_ma).mean().iloc[-1]
                    curr = prices.iloc[-1]
                    if curr > sma * 1.05: risk_level += 1

        debt_info = self.latest_economics_info.get('us_debt')
        if debt_info:
            debt_hist = debt_info.get_history_info(self.today_time, datetime.timedelta(days=self.macro_ma * 2 + 30))
            if debt_hist is not None and not debt_hist.empty:
                prices = None
                if 'Close' in debt_hist.columns: prices = debt_hist['Close']
                elif 'close' in debt_hist.columns: prices = debt_hist['close']
                
                if prices is not None and len(prices) > self.macro_ma:
                    sma = prices.rolling(window=self.macro_ma).mean().iloc[-1]
                    curr = prices.iloc[-1]
                    if curr > sma * 1.05: risk_level += 1
        
        # V3 Logic: 
        # 0 Risks -> 1.0
        # 1 Risk  -> 0.7 (was 0.5)
        # 2 Risks -> 0.4 (was 0.0)
        if risk_level >= 2: return 0.4 
        if risk_level == 1: return 0.7
        return 1.0

    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        choices = []
        stock_data = self.latest_stocks_info[self.ticker]
        today_price = extract_close_price(stock_data, self.today_time)

        if today_price is None or np.isnan(today_price):
            return choices

        shares = self.hold_stock_number.get(self.ticker, 0)
        cash = self.initial_money + self.changed_money
        total_equity = cash + (shares * today_price)

        if total_equity <= 0:
            return choices

        # Cooldown & Stop Loss
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
                self.cooldown_counter = 5 # Reduced cooldown
                return choices

        # Calculations
        hist = stock_data.get_history_price(self.today_time)
        closes = hist["close"].values
        
        if len(closes) < max(self.hurst_window, self.regime_ma) + 10:
            return choices

        # Volatility (Target 35%)
        returns = pd.Series(closes).pct_change().dropna()
        if len(returns) < 20: return choices
        realized_vol = returns.tail(20).std() * np.sqrt(252)
        if realized_vol == 0: realized_vol = 0.01
        
        vol_scalar = self.target_vol / realized_vol
        vol_scalar = min(vol_scalar, 1.0) 

        # Regime (EMA 100)
        ema_regime = pd.Series(closes).ewm(span=self.regime_ma, adjust=False).mean().iloc[-1]
        is_bull_regime = today_price > ema_regime
        
        # Hurst
        H, _ = math_util.rs_analysis_scientific(closes[-self.hurst_window:])
        is_trending = H > self.hurst_threshold
        
        # Macro
        macro_mult = self._get_macro_risk()
        
        target_pct = 0.0
        
        if is_bull_regime:
            if is_trending:
                target_pct = 1.0 * vol_scalar * macro_mult
            else:
                # In Bull Regime but choppy -> Keep exposure but reduce slightly
                target_pct = 0.8 * vol_scalar * macro_mult
        else:
            # Bear Regime
            # V3: If Trend is SUPER strong (H>0.65), allow small position even in Bear Regime (Contrarian/Reversal)
            if H > 0.65:
                 target_pct = 0.3 * vol_scalar * macro_mult
            else:
                 target_pct = 0.0
                 self.max_price = 0
            
        # Execution
        target_value = total_equity * target_pct
        current_value = shares * today_price
        diff_value = target_value - current_value
        
        if abs(diff_value) > total_equity * 0.05 or (shares == 0 and target_pct > 0) or (target_pct == 0 and shares > 0):
            if diff_value > 0:
                num = diff_value / today_price
                choices.append({self.ticker: (buy_or_sell_choice.Buy, num)})
                if shares == 0: self.max_price = today_price
            elif diff_value < 0:
                num = abs(diff_value) / today_price
                choices.append({self.ticker: (buy_or_sell_choice.Sell, num)})
                
        return choices
