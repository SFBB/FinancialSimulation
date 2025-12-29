
import datetime
import os
from utility.simulation_kernel import simulation_kernel
from strategies.strategies import AlphabetFCFStrategy # Import relevant strategies
from strategies.moutai_strategy import MoutaiStrategy
from utility.notifier import Notifier

def run_daily_check():
    print("--- Starting Daily Check ---")
    
    # 1. Configuration
    # We can ask user to specify which strategy to run, or run a default list.
    # For demonstration, let's run MoutaiStrategy (AKShare) and Alphabet (Yahoo).
    strategies_to_run = [
        # (StrategyClass, kwargs, SourceName)
        (MoutaiStrategy, {}, "MoutaiStrategy"),
        # (AlphabetFCFStrategy, {'fast_ma': 20, 'slow_ma': 60}, "AlphabetStrategy")
    ]
    
    # 2. Setup Notifier
    # Ensure keys are set in env or prompt user
    notifier = Notifier()
    recipient_email = os.environ.get("RECIPIENT_EMAIL", "test@example.com")
    
    decisions_summary = []

    for StratClass, kwargs, name in strategies_to_run:
        print(f"\nRunning {name}...")
        
        # 3. Initialize Kernel
        # Start from enough history to form indicators (e.g. 365 days ago)
        # End at NOW (Today)
        # Using TBC (To Be Confirmed) end_time? No, use now()
        start_time = datetime.datetime.now() - datetime.timedelta(days=365)
        end_time = datetime.datetime.now()
        
        sk = simulation_kernel(start_time, end_time, datetime.timedelta(days=1))
        
        # Instantiate Strategy
        # Note: Strategy usually asks for stock_info inside its __init__ or initialize.
        # We need to ensure the strategy uses the correct source if it hardcodes it.
        # MoutaiStrategy likely uses "600519". If we updated it to use 'source', great.
        # If not, we might need to patch it or ensure stock_info defaults work.
        strategy = StratClass(**kwargs)
        sk.add_strategy(strategy)
        
        # 4. Run Simulation
        sk.initialize()
        sk.run()
        sk.end()
        
        # 5. Check for NEW decisions (Today)
        # We look at the LAST record in the strategy.
        if hasattr(strategy, 'get_investment_records'):
            all_records = strategy.get_investment_records()
        else:
             # Fallback (should not be needed if strategy_base is updated)
             print(f"Strategy {name} does not have get_investment_records method.")
             continue

        if not all_records:
            print(f"No trades generated for {name}.")
            continue
            
        last_record = all_records[-1]
        last_date = pd.to_datetime(last_record['time']).date() if 'time' in last_record else None
        today_date = datetime.datetime.now().date()
        
        # Check if the last trade was TODAY (or yesterday if run strictly after close)
        # For "Real-Time", we might care if it's "Recent" (e.g. last 24h).
        if last_date == today_date:
            action = last_record['choice']
            symbol = last_record['stock_info'].ticket_name
            price = last_record['price']
            msg = f"[{name}] {action} {symbol} at ${price:.2f} on {last_date}"
            decisions_summary.append(msg)
            print(f"NEW SIGNAL: {msg}")
        else:
            print(f"Last trade was on {last_date} (No new signal for today)")

    # 6. Notify
    if decisions_summary:
        print("\nSending Notification...")
        notifier.send_decision(recipient_email, decisions_summary)
    else:
        print("\nNo new signals to notify.")

if __name__ == "__main__":
    import pandas as pd # Ensure pandas is available
    run_daily_check()
