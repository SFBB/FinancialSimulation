from utility.simulation_kernel import simulation_kernel
from strategies.tech_trinity_strategy import Tech_Trinity_Strategy
import datetime

if __name__ == "__main__":
    print("--- Running Simulation: Tech Trinity Portfolio (AAPL+MSFT+GOOGL) ---")
    print("Goal: Diversified Alpha via 1/N Allocation & Ultimate Strategy Logic.")
    
    start_date = datetime.datetime(2005, 1, 1)
    end_date = datetime.datetime(2024, 12, 1)
    
    sk = simulation_kernel(
        start_date,
        end_date,
        datetime.timedelta(days=1),
    )
    
    strategy = Tech_Trinity_Strategy(
        tickers=["AAPL", "MSFT", "GOOGL"],
        buy_score=12.0,
        sell_score=8.0,
        target_vol=0.35,
        regime_ma=100
    )
    
    sk.add_strategy(strategy)
    sk.initialize()
    sk.run()
    sk.end()
