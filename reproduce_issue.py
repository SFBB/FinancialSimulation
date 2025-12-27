
import datetime
import pandas as pd
import os
from utility.stock_util import stock_info

def check_index_type():
    print("--- Checking Stock Info Index Type ---")
    # Use a mock interval and dates
    start = datetime.datetime(2023, 1, 1)
    end = datetime.datetime(2023, 1, 10)
    interval = datetime.timedelta(days=1)
    
    # Ensure cache directory exists, or clear it for clean test (optional)
    # create a stock_info instance
    si = stock_info("AAPL", start, end, interval)
    
    # Initialize (fetch or load)
    print("Initializing stock_info...")
    si.initialize()
    
    df = si.history_price_data
    if df.empty:
        print("DataFrame is empty!")
        return

    print("Index names:", df.index.names)
    
    if "date" in df.index.names:
        dates = df.index.get_level_values("date")
        print("First few dates:", dates[:5])
        print("Type of first element:", type(dates[0]))
        
        # Test get_history_price
        print("Testing get_history_price...")
        try:
            hp = si.get_history_price(end)
            print(f"get_history_price returned {len(hp)} rows.")
            print("Successfully retrieved history price.")
        except Exception as e:
            print(f"get_history_price FAILED: {e}")
            
    else:
        print("'date' not in index names.")

if __name__ == "__main__":
    check_index_type()
