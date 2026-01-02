from utility.simulation_kernel import simulation_kernel
from strategies.aapl_dividend_growth import AAPL_Dividend_Growth_Strategy
import datetime
import os

# Clear cache to be safe
cache_file = "cache/yahoo_finance_AAPL_cache_1.pkl"
if os.path.exists(cache_file):
    try:
        os.remove(cache_file)
    except:
        pass

if __name__ == "__main__":
    print("--- Running Simulation: AAPL Dividend Growth (Chowder Rule) ---")
    print("Goal: Yield + Growth > 12.")
    
    # Start from 2018 (AAPL reinstated dividends in 2012, so 2017 is earliest 5y CAGR)
    start_date = datetime.datetime(2018, 1, 1)
    end_date = datetime.datetime(2024, 12, 1)
    
    sk = simulation_kernel(
        start_date,
        end_date,
        datetime.timedelta(days=1),
    )
    
    strategy = AAPL_Dividend_Growth_Strategy(
        ticker="AAPL", 
        buy_score=12.0, 
        sell_score=8.0,
        trend_ma=100
    )
    
    sk.add_strategy(strategy)
    sk.initialize()
    sk.run()
    sk.end()
