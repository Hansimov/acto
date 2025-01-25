"""
Period dict:
    - type:
        - 'match'
            - value: (str) ISO-Format, some chars might be replaced with '*'
        - 'interval'
            - value: (int)
            - unit: 'second', 'minute', 'hour', 'day', 'week', 'month', 'year'
            - at: (str) ISO-Format
        - 'range'
"""


class Perioder:
    def __init__(self, periods: list[dict]):
        self.periods = periods

    def bind(self, func: callable):
        pass

    def echo(self):
        pass

    def monitor(self):
        pass

    def run(self):
        pass
