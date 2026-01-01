from utility.simulation_kernel import *
from strategies.strategies import *
import datetime

if __name__ == "__main__":
    # print("--- Running Simulation with 20/60 MA ---")
    # sk1 = simulation_kernel(datetime.datetime(2022, 1, 1), datetime.datetime.now(), datetime.timedelta(days=1))
    # sk1.add_strategy(AlphabetFCFStrategy(fast_ma=20, slow_ma=60))
    # sk1.initialize()
    # sk1.run()
    # sk1.end()
    #
    # print("\n" + "="*50 + "\n")
    #
    # print("--- Running Simulation with 10/50 MA ---")
    # sk2 = simulation_kernel(datetime.datetime(2022, 1, 1), datetime.datetime.now(), datetime.timedelta(days=1))
    # sk2.add_strategy(AlphabetFCFStrategy(fast_ma=10, slow_ma=50))
    # sk2.initialize()
    # sk2.run()
    # sk2.end()

    # print("--- Running Simulation: ETH-USD Crypto Fractal Trend Strategy ---")
    # sk = simulation_kernel(
    #     datetime.datetime(2022, 1, 1),
    #     datetime.datetime.now(),
    #     datetime.timedelta(days=1),
    # )
    # sk.add_strategy(CryptoTrendStrategy(ticker="ETH-USD", er_window=20))
    # sk.initialize()
    # sk.run()
    # sk.end()

    print("--- Running Simulation: ETH-USD Crypto Fractal Trend Strategy ---")
    sk = simulation_kernel(
        datetime.datetime(2022, 1, 1),
        datetime.datetime.now(),
        datetime.timedelta(days=1),
    )
    sk.add_strategy(AAPL_Quantamental_Strategy())
    sk.initialize()
    sk.run()
    sk.end()
