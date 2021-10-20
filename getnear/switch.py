from getnear import eseries
from getnear import tseries


def connect(hostname, *args, **kwargs):
    for implementation in (eseries, tseries):
        instance = implementation.connect(hostname, *args, **kwargs)
        if instance:
            return instance

    raise Exception(f'unknown switch type for {hostname}:\n{html[:2000]}')
