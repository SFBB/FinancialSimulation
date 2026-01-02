import datetime
import pandas as pd
import numpy as np
from utility.stock_util import stock_info
from utility.math_util import math_util

# Test on assets that showed some promise or are efficient
TICKERS = ["AAPL", "ETH-USD", "GOOGL"]

def test_window_sensitivity():
    print(f"Testing Hurst Sensitivity to Time Window...")
    print(f"{'-'*80}")
    print(f"{'Ticker':<10} | {'Window':<12} | {'Hurst (Sci)':<12} | {'Interpretation'}")
    print(f"{'-'*80}")

    end_time = datetime.datetime.now()
    # Fetch max available data (approx 5 years)
    start_time_max = end_time - datetime.timedelta(days=365*5)
    
    for ticker in TICKERS:
        try:
            # 1. Fetch Data
            # Note: We rely on cache mostly, but let's try to load enough
            si = stock_info(ticker, start_time_max, end_time, datetime.timedelta(days=1))
            si.initialize()
            
            if si.history_price_data.empty:
                print(f"{ticker:<10} | No Data")
                continue
                
            full_prices = si.history_price_data['close'].values
            
            # 2. Define Windows
            # Window sizes in days (trading days approx)
            windows = {
                "3 Months": 60,
                "6 Months": 120,
                "1 Year": 252,
                "2 Years": 504,
                "5 Years": 1260
            }
            
            for label, size in windows.items():
                if len(full_prices) < size:
                    H = np.nan
                else:
                    # Take the MOST RECENT window of this size
                    # This tells us: "If I measured H right now using X months of data..."
                    recent_prices = full_prices[-size:]
                    H, _ = math_util.rs_analysis_scientific(recent_prices)
                
                interp = "-"
                if not np.isnan(H):
                    if H > 0.6: interp = "**Strong Trend**"
                    elif H > 0.55: interp = "Weak Trend"
                    elif H < 0.4: interp = "Mean Rev"
                    else: interp = "Random"
                    
                print(f"{ticker:<10} | {label:<12} | {H:.4f}       | {interp}")
            
            print(f"{'-'*80}")
            
        except Exception as e:
            print(f"{ticker:<10} | Error: {e}")

if __name__ == "__main__":
    test_window_sensitivity()
