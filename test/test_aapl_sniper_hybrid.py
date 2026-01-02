from utility.simulation_kernel import simulation_kernel
from strategies.aapl_sniper import AAPL_Sniper_Hybrid_Strategy
import datetime

if __name__ == "__main__":
    print("--- Running Simulation: AAPL Sniper Hybrid (Precision + VolControl) ---")
    
    start_date = datetime.datetime(2005, 1, 1)
    end_date = datetime.datetime.now()
    
    sk = simulation_kernel(
        start_date,
        end_date,
        datetime.timedelta(days=1),
    )
    
    # Hybrid Configuration
    # RSI < 45 Entry (Sniper)
    # EMA 200 Trend Filter (Sniper)
    # Target Vol 35% (V3 Aggressive)
    # Macro Risk Check (V3)
    strategy = AAPL_Sniper_Hybrid_Strategy(
        ticker="AAPL",
        trend_ma=200,
        entry_rsi=45,
        profit_rsi=80,
        stop_atr_wide=3.0,
        stop_atr_tight=1.0,
        target_vol=0.35,
        macro_ma=50
    )
    
    sk.add_strategy(strategy)
    sk.initialize()
    sk.run()
    sk.end()
