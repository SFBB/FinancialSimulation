import datetime
from abc import ABC, abstractmethod
from .stock_util import stock_info, buy_or_sell_choice, promise_buy, promise_sell, extract_close_price, extract_volume, extract_open_price
from .economic_util import economic_info_base
from .math_util import math_util
import csv
import numpy as np
import pandas as pd
from dataclasses import dataclass
from enum import Enum

class Market(Enum):
    US = "US"
    CN = "CN"

class ExecutionMode(Enum):
    CLOSE_TO_CLOSE = "Close"       # Current: Buy at today's close (Optimistic)
    NEXT_OPEN = "NextOpen"         # Realistic: Signal today, Buy tomorrow Open

@dataclass
class MarketConfig:
    market_type: Market
    commission_rate: float
    min_commission: float
    tax_rate: float # Stamp duty (usually only on sell)
    settlement: str # 'T+0' or 'T+1'
    slippage_rate: float = 0.001   # 0.1% price impact/spread
    volume_limit_pct: float = 0.1  # Max 10% of daily volume allowed to trade
    execution_mode: ExecutionMode = ExecutionMode.CLOSE_TO_CLOSE
    
    @staticmethod
    def US_Market():
        return MarketConfig(
            market_type=Market.US, 
            commission_rate=0.00025, 
            min_commission=5.0, 
            tax_rate=0.0, 
            settlement='T+0',
            slippage_rate=0.0005, # tighter slippage for US (0.05%)
            volume_limit_pct=0.1,
            execution_mode=ExecutionMode.CLOSE_TO_CLOSE
        )
        
    @staticmethod
    def CN_Market():
        # A-Share: 0.025% commission (min 5), 0.05% Tax on Sell (Stamp Duty)
        # Slippage: 0.2% (approx), Vol Limit: 10%
        return MarketConfig(
            market_type=Market.CN, 
            commission_rate=0.00025, 
            min_commission=5.0, 
            tax_rate=0.0005, 
            settlement='T+1',
            slippage_rate=0.001, # 0.1% Slippage
            volume_limit_pct=0.1, # Max 10% of daily volume
            execution_mode=ExecutionMode.CLOSE_TO_CLOSE
        )


class investment_record(ABC):
    def __init__(self, market_config: MarketConfig):
        self.market_config = market_config
        self.records = []
        self.daily_equity = []  # List of dicts: {'time': datetime, 'equity': float}

    def record_daily_equity(self, date_time: datetime.datetime, equity: float):
        self.daily_equity.append({"time": date_time, "equity": equity})

    def handle_choice(self, date_time: datetime.datetime, stock_info: stock_info, choice: buy_or_sell_choice, number: float, total_money: float, total_number: float, force_price: float = None) -> tuple[float, float]:
        if choice == buy_or_sell_choice.DoNothing:
            return 0, 0
        
        if force_price is not None:
             raw_price = force_price
        else:
             raw_price = extract_close_price(stock_info, date_time)
             
        if raw_price is None:
            return 0, 0
            
        # Apply Slippage to Price
        # Buy: Higher Price, Sell: Lower Price
        if choice == buy_or_sell_choice.Buy:
            price = raw_price * (1 + self.market_config.slippage_rate)
        elif choice == buy_or_sell_choice.Sell:
            price = raw_price * (1 - self.market_config.slippage_rate)
        else:
            price = raw_price

        asset_value = price * number
        delta_asset_value = asset_value
        delta_number = number
        if choice == buy_or_sell_choice.Buy:
            if asset_value > total_money:
                # Recalculate max number based on slipped price
                asset_value = total_money
                number = asset_value / price # adjusted number
            delta_asset_value = -asset_value
            delta_number = number
        elif choice == buy_or_sell_choice.Sell:
            if number > total_number:
                number = total_number
                asset_value = price * number
            delta_asset_value = asset_value
            delta_number = -number
        if number == 0:
            return 0, 0
        
        # Calculate Cost based on MarketConfig
        total_cost = 0
        if choice == buy_or_sell_choice.Buy:
            # Usually tax is 0 on Buy for both, commission applies
            comm = max(asset_value * self.market_config.commission_rate, self.market_config.min_commission)
            total_cost = comm
        elif choice == buy_or_sell_choice.Sell:
            comm = max(asset_value * self.market_config.commission_rate, self.market_config.min_commission)
            tax = asset_value * self.market_config.tax_rate # Stamp Duty
            total_cost = comm + tax
        
        # Append record
        self.records.append({
            "time": date_time,
            "price": raw_price, # Record RAW price for reference
            "execution_price": price, # Record Actual executed price
            "stock_info": stock_info,
            "choice": choice,
            "number": number,
            "money_value": asset_value,
            "delta_money_value": delta_asset_value - total_cost,
            "delta_number": delta_number,
            "cost": total_cost,
            "slippage_cost": abs(price - raw_price) * number
        })
        
        return delta_asset_value - total_cost, delta_number

    def get_records(self):
        return self.records.copy()

    def get_statistics(self, initial_capital, risk_free_rate=0.0):
        if not self.daily_equity:
            return {}
        
        df = pd.DataFrame(self.daily_equity)
        if df.empty:
             return {}
        df.set_index("time", inplace=True)
        # Sort index to ensure chronological order
        df.sort_index(inplace=True)
        
        final_equity = df["equity"].iloc[-1]
        total_return = (final_equity - initial_capital) / initial_capital
        
        # Drawdown
        rolling_max = df["equity"].cummax()
        drawdown = (df["equity"] - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        # CAGR (Annualized Return)
        duration_days = (df.index[-1] - df.index[0]).days
        if duration_days > 0:
            cagr = (final_equity / initial_capital) ** (365 / duration_days) - 1
        else:
            cagr = 0
            
        # Sharpe Ratio (Daily Returns)
        df["daily_return"] = df["equity"].pct_change().fillna(0)
        mean_return = df["daily_return"].mean()
        std_return = df["daily_return"].std()
        
        # Annualized Sharpe (assuming 252 trading days)
        sharpe_ratio = 0
        if std_return > 0:
            sharpe_ratio = (mean_return - risk_free_rate/252) / std_return * np.sqrt(252)
            
        return {
            "Start Date": df.index[0].strftime("%Y-%m-%d"),
            "End Date": df.index[-1].strftime("%Y-%m-%d"),
            "Duration (Days)": duration_days,
            "Final Equity": final_equity,
            "Total Return": total_return,
            "CAGR": cagr,
            "Max Drawdown": max_drawdown,
            "Sharpe Ratio": sharpe_ratio,
            "Trades": len(self.records)
        }

class strategy_base(ABC):
    def __init__(self, market_config: MarketConfig = MarketConfig.US_Market()):
        self.market_config = market_config
        self.__investments_info__ = investment_record(market_config)
        self.stock_names = [] # list[str]
        self.latest_stocks_info = {}
        self.latest_economics_info = {}
        self.today_time = datetime.datetime.now()

        self.initial_money = 0
        self.changed_money = 0

        self.hold_stock_number = {}
        self.frozen_stock = {} # {ticket: number} - for T+1 settlement
        self.queued_orders = [] # list of dicts: {ticket, action, amount}

        self.promises = [] # list[promise_base]

        self.initialized = False

    def get_stock_names(self):
        return self.stock_names

    def tick(self, latest_stocks_info: dict[str, stock_info], latest_economics_info: dict[str, economic_info_base], current_time: datetime.datetime):
        if not self.initialized:
            for ticket in self.stock_names:
                self.hold_stock_number[ticket] = 0
                self.frozen_stock[ticket] = 0
            self.initialized = True

        self.latest_stocks_info = latest_stocks_info
        self.latest_economics_info = latest_economics_info
        self.today_time = current_time
        
        # T+1 Settlement: Unfreeze stocks at the start of a new day
        # Since tick represents a new decision point (usually daily), we clear frozen stocks here.
        # This means anything bought "yesterday" (previous tick) is now available.
        if self.market_config.settlement == 'T+1':
            for ticket in self.stock_names:
                self.frozen_stock[ticket] = 0

        # Process Queued Orders (Next-Day Execution)
        # We execute them using TODAY'S Open Price (which is the "Next Day" relative to when the signal was generated)
        queued_to_process = self.queued_orders.copy()
        self.queued_orders = [] # Clear queue
        
        for order in queued_to_process:
            ticket = order['ticket']
            action = order['action']
            amount = order['amount']
            
            # Execute with OPEN price
            # Note: We pass 'open_price' logic inside handle_choice by modifying it or handling it here.
            # Ideally handle_choice should accept a price directly.
            # I modified investment_record.handle_choice to accept force_price.
            
            if ticket in self.latest_stocks_info:
                open_price = extract_open_price(self.latest_stocks_info[ticket], self.today_time)
                if open_price is not None:
                     self._execute_trade(ticket, action, amount, execution_price=open_price)
                else:
                     print(f"Skipping queued order for {ticket}: No Open Price for {self.today_time}")

        # we allow strategy to re-think every tick.
        choice_list = self.make_choice()
        choice_list += self.handle_promises()
        for choice in choice_list:
             # Regular processing for current-day choices
             self.handle_choice(choice)
            
        # Track Daily Equity
        current_equity = self.initial_money + self.changed_money
        all_prices_valid = True
        for ticket in self.stock_names:
            if ticket in self.latest_stocks_info:
                price = extract_close_price(self.latest_stocks_info[ticket], self.today_time)
                if price is not None:
                    current_equity += self.hold_stock_number.get(ticket, 0) * price
                else:
                    # If any stock price is missing (e.g. holiday), skip recording equity for this day 
                    # to avoid fake drawdowns.
                    all_prices_valid = False
                    break
        
        if all_prices_valid:
            self.__investments_info__.record_daily_equity(self.today_time, current_equity)

    def initialize(self):
        pass

    def handle_promises(self):
        choice_list = []
        promised_list = []
        for promise in self.promises:
            do_it, choice = promise.do_promise_or_not(self.today_time)
            if do_it:
                promised_list.append(promise)
                choice_list.append({promise.ticket_name: (choice, promise.number)})
        for promised in promised_list:
            self.promises.remove(promised)
        return choice_list

    # Renaming this to _process_signal to avoid confusion, but keeping name for compatibility for now.
    # This acts as the "Signal Receiver"
    def handle_choice(self, choice):
        for ticket in choice.keys():
            action, amount = choice[ticket]
            
            if self.market_config.execution_mode == ExecutionMode.NEXT_OPEN:
                 # Queue for next day
                 self.queued_orders.append({'ticket': ticket, 'action': action, 'amount': amount})
                 # print(f"Queued order for {ticket}: {action} {amount}")
            else:
                 # Execute immediately (Close-to-Close)
                 self._execute_trade(ticket, action, amount)

    def _execute_trade(self, ticket, action, amount, execution_price=None):
            # T+1 Validation for Sell
            if action == buy_or_sell_choice.Sell and self.market_config.settlement == 'T+1':
                available = self.hold_stock_number.get(ticket, 0) - self.frozen_stock.get(ticket, 0)
                if amount > available:
                    # Cap sell amount to available shares
                    print(f"Refusing to sell frozen shares for {ticket}. Requested: {amount}, Available: {available}")
                    amount = available
                    if amount <= 0:
                        return # Skip this trade
            
            # Liquidity / Volume Limit Validation
            if self.market_config.volume_limit_pct < 1.0:
                daily_vol = extract_volume(self.latest_stocks_info[ticket], self.today_time)
                if daily_vol > 0:
                    max_shares = daily_vol * self.market_config.volume_limit_pct
                    if amount > max_shares:
                        print(f"Liquidity Crunch for {ticket}: Requested {amount} shares, but Day Volume was {daily_vol}. Capping at {max_shares:.2f} (10% limit).")
                        amount = max_shares
            
            changed_value, changed_number = self.__investments_info__.handle_choice(
                self.today_time,
                self.latest_stocks_info[ticket],
                action,
                amount,
                self.initial_money + self.changed_money,
                self.hold_stock_number[ticket],
                force_price=execution_price
            )
            self.changed_money += changed_value
            if action != buy_or_sell_choice.DoNothing:
                if ticket not in self.hold_stock_number.keys():
                    self.hold_stock_number[ticket] = 0
                self.hold_stock_number[ticket] += changed_number
                
                # T+1 Logic: Freeze bought shares
                if action == buy_or_sell_choice.Buy and self.market_config.settlement == 'T+1':
                     if ticket not in self.frozen_stock: self.frozen_stock[ticket] = 0
                     self.frozen_stock[ticket] += changed_number


    def new_promise(self, promise):
        self.promises.append(promise)

    @abstractmethod
    def end(self):
        pass

    @abstractmethod
    def make_choice(self) -> list[dict[str, tuple[buy_or_sell_choice, float]]]:
        return {}

    def print_performance_report(self):
        stats = self.__investments_info__.get_statistics(self.initial_money)
        
        print(f"\n{'='*40}")
        # Try to get strategy name if implemented, else use class name
        name = self.get_name() if hasattr(self, 'get_name') else self.__class__.__name__
        print(f"Strategy Report: {name}")
        
        # Market Info
        mkt_type = "US (T+0)" if self.market_config.market_type == Market.US else "A-Shares (CN) [T+1 Settlement]"
        print(f"Market: {mkt_type}")
        print(f"{'='*40}")
        
        if stats:
            print(f"Period:            {stats.get('Start Date', 'N/A')} to {stats.get('End Date', 'N/A')}")
            print(f"Duration:          {stats.get('Duration (Days)', 'N/A')} days")
            print(f"Initial Capital:   ${self.initial_money:,.2f}")
            print(f"Final Equity:      ${stats['Final Equity']:,.2f}")
            print(f"Total Return:      {stats['Total Return'] * 100:.2f}%")
            print(f"CAGR:              {stats['CAGR'] * 100:.2f}%")
            print(f"Max Drawdown:      {stats['Max Drawdown'] * 100:.2f}%")
            print(f"Sharpe Ratio:      {stats['Sharpe Ratio']:.2f}")
            print(f"Total Trades:      {stats['Trades']}")
        else:
            print("No trades or insufficient data for statistics.")
        print(f"{'='*40}\n")
