from utility.simulation_kernel import simulation_kernel
from strategies.aapl_dividend_strategy import AAPL_Dividend_Strategy
import datetime
import os

# Clear cache to ensure dividends are present
cache_file = "cache/yahoo_finance_AAPL_cache_1.pkl"
if os.path.exists(cache_file):
    os.remove(cache_file)

if __name__ == "__main__":
    print("--- Running Simulation: AAPL Dividend Yield Strategy ---")
    print("Goal: Buy Dips (Yield > 0.6%), Sell Bubbles (Yield < 0.3%).")
    
    start_date = datetime.datetime(2015, 1, 1)
    end_date = datetime.datetime(2024, 12, 1)
    
    sk = simulation_kernel(
        start_date,
        end_date,
        datetime.timedelta(days=1),
    )
    
    strategy = AAPL_Dividend_Strategy(
        ticker="AAPL", 
        buy_yield=0.006,  # 0.6%
        sell_yield=0.003, # 0.3%
        trend_ma=100
    )
    
    sk.add_strategy(strategy)
    sk.initialize()
    sk.run()
    sk.end()
