import numpy as np
# import matplotlib.pyplot as plt
import warnings



class math_util:
    @staticmethod
    @staticmethod
    def divide_chunks(l, n):
        for i in range(0, len(l), n):
            yield l[i: i+n]
    @staticmethod
    def rs_analysis(x, min_chunk_size):
        if min_chunk_size < 2:
            min_chunk_size = 2
        N = len(x)
        rs_series = []
        n_series = []
        # 1. The series is divided into chunks of chunk_size_list size
        chunk_size = min_chunk_size
        while chunk_size < len(x):
            rs_n_list = []
            for start_index in range(0, len(x) - chunk_size, chunk_size):
                x_n = x[start_index : start_index + chunk_size]
                z_t = np.cumsum(x_n - np.mean(x_n))
                r_n = np.max(z_t) - np.min(z_t)
                s_n = np.nanstd(x_n)
                rs_n = 1.0
                if not np.abs(s_n) < 0.0001:
                    rs_n = np.divide(r_n, s_n)
                rs_n_list.append(rs_n)
            rs_series.append(np.nanmean(rs_n_list))
            n_series.append(chunk_size)

            # We increment index by 1 per sampling.
            chunk_size = 2 * chunk_size

        # plt.plot(np.log(n_series), np.log(rs_series))
        # plt.plot(np.arange(np.log(n_series)[0], np.log(n_series)[-1]), 0.5 * np.arange(np.log(n_series)[0], np.log(n_series)[-1]))
        # 3. calculate the Hurst exponent.
        H, c = np.linalg.lstsq(
            a=np.vstack((np.log(n_series), np.ones(len(n_series)))).T,
            b=np.log(rs_series),
            rcond=None
        )[0]
        # plt.plot(np.arange(np.log(n_series)[0], np.log(n_series)[-1]), H * np.arange(np.log(n_series)[0], np.log(n_series)[-1]) + c)
        # plt.show()

        return H, c

    @staticmethod
    def calc_trending_rate_with_polyfit(x, n=3):
        x_i = np.linspace(0, 1, len(x))
        z = np.polyfit(x_i, x, n)
        p = np.poly1d(z)
        p_2 = np.polyder(p, 1)
        # _ = plt.plot(x_i, x, '-', x_i, p(x_i), "--")
        # plt.show()
        return p_2(1) / list(x)[-1]

    @staticmethod
    def calc_trending_rate_with_lstd(x):
        x_i = np.linspace(0, 1, len(x))
        k, c = np.linalg.lstsq(
            a=np.vstack((x_i, np.ones(len(x_i)))).T,
            b=x,
            rcond=None
        )[0]
        return k / list(x)[-1]
        
    @staticmethod
    def calc_trending_rate_with_simple_method(x):
        # x_i = np.linspace(0, 1, len(x))
        k = (list(x)[-1] - list(x)[0])
        # p = np.poly1d([k, list(x)[0]])
        # _ = plt.plot(x_i, x, '-', x_i, p(x_i), "--")
        # plt.show()
        return k / list(x)[-1]

    @staticmethod
    def rs_analysis_scientific(prices, min_chunk_size=8):
        """
        Scientific implementation of Hurst Exponent using R/S analysis on Log Returns.
        """
        # 1. Compute Log Returns
        prices = np.array(prices, dtype=float)
        if len(prices) < min_chunk_size * 2:
            return 0.5, 0 # Not enough data

        # Log returns: ln(Pt / Pt-1)
        # Note: We take log based differences.
        log_returns = np.diff(np.log(prices))
        
        # 2. R/S Analysis on Log Returns
        x = log_returns
        N = len(x)
        
        rs_series = []
        n_series = []
        
        # Dense sampling of chunk sizes (logarithmically spaced)
        # From min_chunk_size to N/2
        min_log = np.log10(min_chunk_size)
        max_log = np.log10(N / 1) # Use full length if possible? Usually up to N.
        # But R/S is usually calculated on sub-chunks. 
        # Range: min_chunk to N
        
        # Let's use specific chunk sizes: roughly 30 points log-spaced
        chunk_sizes = np.unique(np.logspace(min_log, max_log, num=20).astype(int))
        chunk_sizes = chunk_sizes[chunk_sizes <= N]
        chunk_sizes = chunk_sizes[chunk_sizes >= min_chunk_size]
        
        for n in chunk_sizes:
            # Split x into N/n chunks
            # We use non-overlapping chunks for simplicity and robustness
            num_chunks = N // n
            if num_chunks < 1:
                continue
                
            rs_values = []
            for i in range(num_chunks):
                start = i * n
                end = start + n
                chunk = x[start:end]
                
                # R/S calculation for this chunk
                mean = np.mean(chunk)
                y = chunk - mean # Mean centered
                z = np.cumsum(y) # Cumulative deviation
                
                # Range
                R = np.max(z) - np.min(z)
                
                # Standard Deviation
                S = np.std(chunk, ddof=1) # Sample standard deviation
                
                if S == 0:
                    continue
                    
                rs_values.append(R / S)
            
            if len(rs_values) > 0:
                rs_series.append(np.mean(rs_values))
                n_series.append(n)
        
        if len(n_series) < 3:
             return 0.5, 0 # Failed regression

        # 3. Log-Log Regression
        # log(R/S) ~ H * log(n) + c
        log_n = np.log(n_series)
        log_rs = np.log(rs_series)
        
        # Fit line
        H, c = np.linalg.lstsq(
            a=np.vstack((log_n, np.ones(len(log_n)))).T,
            b=log_rs,
            rcond=None
        )[0]
        
        return H, c




if __name__ == "__main__":
    number = 1000
    x = np.random.rand(number)
    H, c = math_util.rs_analysis(x, 2)
    print("H: {}, c: {}".format(H, c))
