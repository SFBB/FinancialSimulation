from utility.simulation_kernel import simulation_kernel
from strategies.moutai_valuation_strategy import Moutai_Valuation_Strategy
import datetime

if __name__ == "__main__":
    print("--- Running Simulation: Moutai Valuation Strategy (PE + Trend) ---")
    print("Goal: Buy Low PE (<35), Sell High PE (>55).")
    
    # Simulate from 2015 to cover the full bull-bear cycle
    start_date = datetime.datetime(2015, 1, 1)
    end_date = datetime.datetime(2024, 12, 1)
    
    sk = simulation_kernel(
        start_date,
        end_date,
        datetime.timedelta(days=1),
    )
    
    strategy = Moutai_Valuation_Strategy(
        ticker="600519.SS", 
        buy_pe=35,
        sell_pe=55,
        trend_ma=20
    )
    
    sk.add_strategy(strategy)
    sk.initialize()
    sk.run()
    sk.end()
