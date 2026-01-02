from utility.simulation_kernel import simulation_kernel
from strategies.tech_trinity_v1_static import Tech_Trinity_Static_Strategy
import datetime

if __name__ == "__main__":
    print("--- Running Simulation: Portfolio V1 (Static Defensive) ---")
    print("Goal: Stability & Preservation (1/N Allocation).")
    
    start_date = datetime.datetime(2010, 6, 29)
    end_date = datetime.datetime(2024, 12, 1)
    
    sk = simulation_kernel(
        start_date,
        end_date,
        datetime.timedelta(days=1),
    )
    
    strategy = Tech_Trinity_Static_Strategy(
        tickers=["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "KO"],
        # V1 Params (Fundamental Focus)
        buy_score=12.0,
        sell_score=8.0,
        hurst_threshold=0.55,
        target_vol=0.35,
        regime_ma=100
    )
    
    sk.add_strategy(strategy)
    sk.initialize()
    sk.run()
    sk.end()
