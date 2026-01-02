from utility.simulation_kernel import simulation_kernel
from strategies.tech_trinity_strategy import Tech_Trinity_Strategy
import datetime

if __name__ == "__main__":
    print("--- Running Simulation: Super Six Portfolio (Tech + Growth + Value) ---")
    print("Assets: AAPL, MSFT, GOOGL, NVDA, TSLA, KO")
    print("Logic: Universal Ultimate Strategy (1/N Allocation).")
    
    # Start from TSLA IPO date to ensure full portfolio participation
    start_date = datetime.datetime(2010, 6, 29)
    end_date = datetime.datetime(2024, 12, 1)
    
    sk = simulation_kernel(
        start_date,
        end_date,
        datetime.timedelta(days=1),
    )
    
    strategy = Tech_Trinity_Strategy(
        tickers=["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "KO"],
        top_k=4,            # Only invest in Top 4 performers
        target_vol=0.40,    # Slightly more aggressive
        hurst_threshold=0.52 
    )
    
    sk.add_strategy(strategy)
    sk.initialize()
    sk.run()
    sk.end()
