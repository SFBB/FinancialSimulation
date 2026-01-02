from utility.simulation_kernel import simulation_kernel
from strategies.moutai_strategy import Moutai_FMH_V3_Strategy
import datetime

if __name__ == "__main__":
    print("--- Running Simulation: Moutai (600519.SS) FMH V3 Strategy ---")
    print("Goal: Apply AAPL V3 logic to A-Shares (Trend + Vol Control).")
    
    start_date = datetime.datetime(2018, 1, 1)
    end_date = datetime.datetime(2024, 12, 1)
    
    sk = simulation_kernel(
        start_date,
        end_date,
        datetime.timedelta(days=1),
    )
    
    strategy = Moutai_FMH_V3_Strategy(
        ticker="600519.SS",
        hurst_threshold=0.55,
        regime_ma=60,      # Faster MA for A-shares
        target_vol=0.25    # 25% Vol Target
    )
    
    sk.add_strategy(strategy)
    sk.initialize()
    sk.run()
    sk.end()