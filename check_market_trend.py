from utility.stock_util import stock_info
import datetime
import pandas as pd

if __name__ == "__main__":
    start_date = datetime.datetime(2022, 1, 1)
    end_date = datetime.datetime.now()
    
    print(f"Checking Market Trend for 600519.SS ({start_date.date()} to {end_date.date()})...")
    
    si = stock_info("600519.SS", start_date, end_date, datetime.timedelta(days=1))
    si.initialize()
    
    history = si.get_history_price(end_date)
    
    if len(history) > 0:
        start_filter = pd.Timestamp(2022, 1, 1)
        history_slice = history.loc[history.index.get_level_values('date') >= start_filter]
        
        if len(history_slice) > 0:
            first_price = history_slice.iloc[0]['close']
            last_price = history_slice.iloc[-1]['close']
            
            start_date_actual = history_slice.index.get_level_values('date')[0]
            end_date_actual = history_slice.index.get_level_values('date')[-1]
            
            change_pct = (last_price - first_price) / first_price
            
            print(f"\n{'='*40}")
            print(f"Analysis Period: 2022-2025")
            print(f"Start Date: {start_date_actual.date()} | Price: {first_price:.2f}")
            print(f"End Date:   {end_date_actual.date()} | Price: {last_price:.2f}")
            print(f"Total Change (Buy & Hold): {change_pct*100:.2f}%")
            print(f"{'='*40}")
        else:
             print("No stock data found for 2022-2025 period.")
    else:
        print("No stock data found.")
