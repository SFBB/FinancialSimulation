from utility.simulation_kernel import simulation_kernel
from strategies.tencent_volume_strategy import Tencent_Volume_Sniper_Strategy
import datetime

if __name__ == "__main__":
    print("--- Running Simulation: Tencent (0700.HK) Volume Sniper ---")
    print("Goal: Buy breakouts from Low Volume Volatility regimes.")
    
    start_date = datetime.datetime(2010, 1, 1)
    end_date = datetime.datetime(2024, 12, 1)
    
    sk = simulation_kernel(
        start_date,
        end_date,
        datetime.timedelta(days=1),
    )
    
    strategy = Tencent_Volume_Sniper_Strategy(
        ticker="0700.HK",
        vol_window=20,
        calm_threshold=0.4, # Adjusted for HK market volatility
        spike_multiplier=1.5
    )
    
    sk.add_strategy(strategy)
    sk.initialize()
    sk.run()
    sk.end()
