
import datetime
import pandas as pd
from utility.stock_util import stock_info

def test_yahoo():
    print("\n--- Testing Yahoo Source (GOOGL) ---")
    end = datetime.datetime.now()
    start = end - datetime.timedelta(days=30)
    
    si = stock_info(
        "GOOGL",
        start,
        end,
        datetime.timedelta(days=1),
        source="yahoo"
    )
    si.initialize()
    
    print(f"Raw Data Shape: {si.raw_data.shape}")
    print(f"Core Data Shape: {si.history_price_data.shape}")
    
    if not si.history_price_data.empty:
        print("Core Columns:", si.history_price_data.columns.tolist())
        latest = si.history_price_data.iloc[-1]
        print(f"Latest Core Data:\n{latest}")
    else:
        print("ERROR: Core Data is empty!")

def test_akshare():
    print("\n--- Testing AKShare Source (600519 - Moutai) ---")
    end = datetime.datetime.now()
    start = end - datetime.timedelta(days=365) # Longer for AKShare to ensure recent data
    
    # 600519 is Moutai
    si = stock_info(
        "600519",
        start,
        end,
        datetime.timedelta(days=1),
        source="akshare"
    )
    si.initialize()
    
    print(f"Raw Data Shape: {si.raw_data.shape}")
    print(f"Core Data Shape: {si.history_price_data.shape}")
    
    if not si.history_price_data.empty:
        print("Core Columns:", si.history_price_data.columns.tolist())
        latest = si.history_price_data.iloc[-1]
        print(f"Latest Core Data:\n{latest}")
    else:
        print("ERROR: Core Data is empty! (Check if AKShare is installed and network is up)")

if __name__ == "__main__":
    try:
        test_yahoo()
    except Exception as e:
        print(f"Yahoo Test Failed: {e}")
        
    try:
        test_akshare()
    except Exception as e:
        print(f"AKShare Test Failed: {e}")
