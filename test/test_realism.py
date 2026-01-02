from utility.simulation_kernel import simulation_kernel
from strategies.tech_trinity_v2_momentum import Tech_Trinity_Momentum_Strategy
from utility.strategy import MarketConfig, ExecutionMode
import datetime

if __name__ == "__main__":
    print("--- Running REALISM CHECK: Super 8 (Includes Losers: NOK, Citigroup) ---")
    print("Logic: Top 4 of 8. Next Open Execution. 0.1% Slippage.")
    
    # Starting from 2005 to cover 2008 crisis
    start_date = datetime.datetime(2005, 1, 1)
    end_date = datetime.datetime(2024, 12, 1)
    
    sk = simulation_kernel(
        start_date,
        end_date,
        datetime.timedelta(days=1),
    )
    
    # Portfolio of 8: Strong, Winners, and historical Losers (NOK, C)
    strategy = Tech_Trinity_Momentum_Strategy(
        tickers=["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "KO", "NOK", "C"],
        top_k=4,
        target_vol=0.40,
        hurst_threshold=0.52 
    )
    
    # --- HARD MODE ENABLED ---
    strategy.market_config.execution_mode = ExecutionMode.NEXT_OPEN
    strategy.market_config.slippage_rate = 0.001 
    
    sk.add_strategy(strategy)
    sk.initialize()
    sk.run()
    sk.end()
