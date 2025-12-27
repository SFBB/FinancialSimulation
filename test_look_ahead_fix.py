from utility.simulation_kernel import simulation_kernel
from strategies.moutai_strategy import MoutaiStrategy
from utility.strategy import ExecutionMode
import datetime

if __name__ == "__main__":
    print("--- Running Look-Ahead Bias Check (Next-Day Open Execution) ---")
    start_date = datetime.datetime(2022, 1, 1)
    end_date = datetime.datetime.now()
    
    sk = simulation_kernel(start_date, end_date, datetime.timedelta(days=1))
    
    strategy = MoutaiStrategy()
    # Force NEXT_OPEN Execution Mode
    strategy.market_config.execution_mode = ExecutionMode.NEXT_OPEN
    
    print(f"Market Config Mode: {strategy.market_config.execution_mode}")
    
    sk.add_strategy(strategy)
    
    print(f"Initializing...")
    sk.initialize()
    print("Running...")
    sk.run()
    
    # Check if we have trades
    if len(strategy.__investments_info__.records) > 0:
        print("First 3 Trades:")
        for r in strategy.__investments_info__.records[:3]:
            # Print execution details
            date = r['time'].strftime('%Y-%m-%d')
            action = r['choice'].name
            price = r['execution_price']
            print(f"  {date}: {action} @ {price:.2f}")
    else:
        print("No trades executed.")
        
    sk.end()
