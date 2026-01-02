from utility.simulation_kernel import simulation_kernel
from strategies.aapl_macro_fmh import AAPL_Macro_FMH_Strategy_V3
import datetime

if __name__ == "__main__":
    print("--- Running Simulation: AAPL Macro FMH Strategy V3 (Aggressive) ---")
    
    start_date = datetime.datetime(2005, 1, 1)
    # Fixed end date ensures cache hits. Using a past date guarantees data availability.
    end_date = datetime.datetime(2024, 12, 1)
    
    sk = simulation_kernel(
        start_date,
        end_date,
        datetime.timedelta(days=1),
    )
    
    strategy = AAPL_Macro_FMH_Strategy_V3(
        ticker="AAPL",
        hurst_threshold=0.55,
        regime_ma=100,
        target_vol=0.35, # Aggressive
        macro_ma=50
    )
    
    sk.add_strategy(strategy)
    sk.initialize()
    sk.run()
    sk.end()
