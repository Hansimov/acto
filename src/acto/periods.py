import time

from tclogger import logger, logstr, brk, get_now_str
from tclogger import shell_cmd, Runtimer
from typing import Union

from .times import PatternedDatetimeSeeker


class Perioder:
    def __init__(self, patterns: Union[str, dict, list]):
        self.patterns = patterns
        self.seeker = PatternedDatetimeSeeker(patterns)

    def bind(self, func: callable):
        self.func = func

    def run(self):
        for dt_str, remain_seconds in self.seeker:
            remain_seconds_str = logstr.file(f"{remain_seconds}s")
            logger.note(
                f"now: {logstr.file(brk(get_now_str()))}, "
                f"next_run: {logstr.file(brk(dt_str))}, "
                f"wait_for: {remain_seconds_str}"
            )
            time.sleep(remain_seconds)
            self.func()


def foo():
    cmd = "date"
    shell_cmd(cmd, showcmd=False)


def test_perioder():
    logger.note("> test_perioder")
    # patterns = "****-**-** **:**:**"
    patterns = {"second": "*[369]"}
    perioder = Perioder(patterns)
    perioder.bind(foo)
    perioder.run()


if __name__ == "__main__":
    with Runtimer():
        test_perioder()

    # python -m acto.periods
