from utility.simulation_kernel import simulation_kernel
from strategies.aapl_ultimate_strategy import AAPL_Ultimate_Strategy
import datetime
import os

# Clear cache to ensure fresh data fetch (max history + dividends)
# cache_file = "cache/yahoo_finance_AAPL_cache_1.pkl"
# if os.path.exists(cache_file):
#     try:
#         os.remove(cache_file)
#     except:
#         pass

if __name__ == "__main__":
    print("--- Running Simulation: AAPL Ultimate All-Weather Strategy ---")
    print("Goal: Trinity of Macro, Fundamental (Div Growth), and Technical (FMH+Vol).")
    
    start_date = datetime.datetime(2005, 1, 1)
    end_date = datetime.datetime(2024, 12, 1)
    
    sk = simulation_kernel(
        start_date,
        end_date,
        datetime.timedelta(days=1),
    )
    
    strategy = AAPL_Ultimate_Strategy(
        ticker="AAPL",
        # Config
        buy_score=12.0,
        sell_score=8.0,
        target_vol=0.35, # Aggressive
        regime_ma=100
    )
    
    sk.add_strategy(strategy)
    sk.initialize()
    sk.run()
    sk.end()
