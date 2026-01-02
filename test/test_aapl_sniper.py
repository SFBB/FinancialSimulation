from utility.simulation_kernel import simulation_kernel
from strategies.aapl_sniper import AAPL_Sniper_Strategy
import datetime

if __name__ == "__main__":
    print("--- Running Simulation: AAPL Sniper Strategy (Precision Timing) ---")
    print("Goal: Capture Bull Dips, Exit on Bear Reversals.")
    
    start_date = datetime.datetime(2005, 1, 1)
    end_date = datetime.datetime.now()
    
    sk = simulation_kernel(
        start_date,
        end_date,
        datetime.timedelta(days=1),
    )
    
    # Sniper Strategy Configuration
    # RSI < 45 for Entry (slightly easier than 40 to ensure we don't miss too many)
    # RSI > 80 for Profit Protect (Tighten stop)
    strategy = AAPL_Sniper_Strategy(
        ticker="AAPL",
        trend_ma=200,      # Bull Market Filter
        entry_rsi=45,      # Sniper Entry (Buy the fear)
        profit_rsi=80,     # Euphoria Level
        stop_atr_wide=3.0, # Normal wiggle room
        stop_atr_tight=1.0 # Tight lock when euphoric
    )
    
    sk.add_strategy(strategy)
    sk.initialize()
    sk.run()
    sk.end()
