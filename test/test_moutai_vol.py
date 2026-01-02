from utility.simulation_kernel import simulation_kernel
from strategies.tencent_volume_strategy import Tencent_Volume_Sniper_Strategy
import datetime

if __name__ == "__main__":
    print("--- Running Simulation: Moutai (600519.SS) Volume Sniper ---")
    print("Goal: Test if Volume Volatility works better on A-Shares (Smart Money).")
    
    start_date = datetime.datetime(2010, 1, 1)
    end_date = datetime.datetime(2024, 12, 1)
    
    sk = simulation_kernel(
        start_date,
        end_date,
        datetime.timedelta(days=1),
    )
    
    # Reusing the Tencent strategy class but applying to Moutai
    # Logic is universal: Low Vol Volatility -> Breakout
    strategy = Tencent_Volume_Sniper_Strategy(
        ticker="600519.SS",
        vol_window=20,
        calm_threshold=0.4, 
        spike_multiplier=1.5
    )
    
    sk.add_strategy(strategy)
    sk.initialize()
    sk.run()
    sk.end()
