from utility.simulation_kernel import simulation_kernel
from strategies.aapl_ultimate_strategy import AAPL_Ultimate_Strategy
import datetime

if __name__ == "__main__":
    print("--- Running Simulation: GOOGL Ultimate All-Weather Strategy ---")
    print("Testing Strategy Generalization on Alphabet (GOOGL).")
    
    start_date = datetime.datetime(2005, 1, 1)
    end_date = datetime.datetime(2024, 12, 1)
    
    sk = simulation_kernel(
        start_date,
        end_date,
        datetime.timedelta(days=1),
    )
    
    # We use the same parameters as AAPL to test robustness
    strategy = AAPL_Ultimate_Strategy(
        ticker="GOOGL",
        buy_score=12.0,
        sell_score=8.0,
        target_vol=0.35,
        regime_ma=100
    )
    
    sk.add_strategy(strategy)
    sk.initialize()
    sk.run()
    sk.end()
