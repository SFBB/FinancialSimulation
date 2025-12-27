from utility.simulation_kernel import simulation_kernel
from strategies.moutai_strategy import MoutaiStrategy
import datetime

if __name__ == "__main__":
    print("--- Running Moutai A-Share Simulation (T+1 Check) ---")
    start_date = datetime.datetime(2022, 1, 1)
    end_date = datetime.datetime.now()
    
    sk = simulation_kernel(start_date, end_date, datetime.timedelta(days=1))
    
    strategy = MoutaiStrategy()
    sk.add_strategy(strategy)
    
    print(f"Initializing for {start_date.date()} to {end_date.date()}...")
    sk.initialize()
    print("Running...")
    sk.run()
    print("Finished. Generating Reports...")
    sk.end()
