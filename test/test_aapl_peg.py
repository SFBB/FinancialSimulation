from utility.simulation_kernel import simulation_kernel
from strategies.aapl_peg_strategy import AAPL_PEG_Strategy
import datetime

if __name__ == "__main__":
    print("--- Running Simulation: AAPL PEG Strategy (Lynch Style) ---")
    print("Goal: Buy Growth at a Reasonable Price (PEG < 1.5).")
    
    # 2021-2024 (Data likely available)
    start_date = datetime.datetime(2021, 1, 1)
    end_date = datetime.datetime(2024, 12, 1)
    
    sk = simulation_kernel(
        start_date,
        end_date,
        datetime.timedelta(days=1),
    )
    
    strategy = AAPL_PEG_Strategy(
        ticker="AAPL", 
        buy_peg=1.5,
        sell_peg=2.5,
        trend_ma=50
    )
    
    sk.add_strategy(strategy)
    sk.initialize()
    sk.run()
    sk.end()
