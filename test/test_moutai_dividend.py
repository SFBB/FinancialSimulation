from utility.simulation_kernel import simulation_kernel
from strategies.moutai_dividend_strategy import Moutai_Dividend_Strategy
import datetime

if __name__ == "__main__":
    print("--- Running Simulation: Moutai Dividend Yield Strategy ---")
    print("Goal: Buy High Yield (>2%), Sell Low Yield (<1%).")
    
    # 2015-2024
    start_date = datetime.datetime(2015, 1, 1)
    end_date = datetime.datetime(2024, 12, 1)
    
    sk = simulation_kernel(
        start_date,
        end_date,
        datetime.timedelta(days=1),
    )
    
    strategy = Moutai_Dividend_Strategy(
        ticker="600519.SS", 
        buy_yield=0.020,  # 2.0%
        sell_yield=0.010, # 1.0%
        trend_ma=20
    )
    
    sk.add_strategy(strategy)
    sk.initialize()
    sk.run()
    sk.end()
