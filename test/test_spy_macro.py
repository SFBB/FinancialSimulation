from utility.simulation_kernel import simulation_kernel
from strategies.aapl_macro_fmh import AAPL_Macro_FMH_Strategy_V3
import datetime

if __name__ == "__main__":
    print("--- Running Simulation: Strategy applied to SPY (The Market) ---")
    
    start_date = datetime.datetime(2005, 1, 1)
    end_date = datetime.datetime.now()
    
    sk = simulation_kernel(
        start_date,
        end_date,
        datetime.timedelta(days=1),
    )
    
    # We use the same V3 logic, but apply it to SPY.
    # Note: SPY volatility is lower than AAPL, so we adjust target_vol to 0.20 (20%)
    # to make the volatility targeting mechanism actually active.
    strategy = AAPL_Macro_FMH_Strategy_V3(
        ticker="SPY",
        hurst_threshold=0.55,
        regime_ma=100,
        target_vol=0.20, 
        macro_ma=50
    )
    
    sk.add_strategy(strategy)
    sk.initialize()
    sk.run()
    sk.end()
