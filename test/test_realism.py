from utility.simulation_kernel import simulation_kernel
from strategies.moutai_strategy import MoutaiStrategy
import datetime

if __name__ == "__main__":
    print("--- Running Realism Check (Slippage + Liquidity Crunch) ---")
    start_date = datetime.datetime(2022, 1, 1)
    end_date = datetime.datetime.now()

    sk = simulation_kernel(start_date, end_date, datetime.timedelta(days=1))

    # Use Massive Capital to trigger Volume Limit (100 Billion)
    strategy = MoutaiStrategy()
    strategy.initial_money = 100_000_000_000

    sk.add_strategy(strategy)

    print(f"Initializing with $100 Billion Capital...")
    sk.initialize()
    print("Running...")
    sk.run()
    sk.end()
