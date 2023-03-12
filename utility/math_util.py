import numpy as np
import matplotlib.pyplot as plt
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
        _ = plt.plot(x_i, x, '-', x_i, p(x_i), "--")
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




if __name__ == "__main__":
    number = 1000
    x = np.random.rand(number)
    H, c = math_util.rs_analysis(x, 2)
    print("H: {}, c: {}".format(H, c))
