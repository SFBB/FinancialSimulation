from utility.simulation_kernel import simulation_kernel
from strategies.aapl_macro_fmh import AAPL_Macro_FMH_Strategy_V2
import datetime

if __name__ == "__main__":
    print("--- Running Simulation: AAPL Macro FMH Strategy V2 (2005-Present) ---")
    
    # Simulate from 2005
    start_date = datetime.datetime(2005, 1, 1)
    end_date = datetime.datetime.now()
    
    sk = simulation_kernel(
        start_date,
        end_date,
        datetime.timedelta(days=1),
    )
    
    # Initialize strategy V2
    strategy = AAPL_Macro_FMH_Strategy_V2(
        ticker="AAPL",
        hurst_threshold=0.55,
        regime_ma=120,    # EMA 120 filter
        target_vol=0.20,  # Target 20% Vol
        macro_ma=50
    )
    
    sk.add_strategy(strategy)
    sk.initialize()
    sk.run()
    sk.end()