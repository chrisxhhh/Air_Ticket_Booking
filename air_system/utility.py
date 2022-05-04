from datetime import datetime


def process_time(time):
    """convert timedelta to printable hour:min string"""
    time = str(time)
    hour, min, second = time.split(':')

    if len(hour) == 2:
        return hour + ':' + min
    else:
        return '0' + hour + ':' + min

