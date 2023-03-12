import datetime
from abc import ABC, abstractmethod



class economic_info_base(ABC):
    def __init__(self, start_time: datetime.datetime, end_time: datetime.datetime, interval: datetime.timedelta):
        self.start_time = start_time
        self.end_time = end_time
        self.interval = interval

    @abstractmethod
    def update(self):
        pass

    @abstractmethod
    def get_today_info(self, current_time: datetime.datetime):
        pass

    @abstractmethod
    def get_history_info(self, current_time: datetime.datetime):
        pass
