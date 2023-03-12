from utility.simulation_kernel import *
from strategies.strategies import *



if __name__ == "__main__":
    sk = simulation_kernel(datetime.datetime(2022, 1, 1), datetime.datetime.now(), datetime.timedelta(days=1))
    sk.add_strategy(GOOGLStrategy())
    sk.initialize()
    sk.run()
    sk.end()
