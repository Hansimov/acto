import time

from datetime import datetime
from pathlib import Path
from tclogger import logger, logstr, brk, decolored, FileLogger
from tclogger import get_now_str, get_now_ts, str_to_ts, dt_to_str
from tclogger import shell_cmd, Runtimer, TCLogbar
from typing import Union

from .times import PatternedDatetimeSeeker


class Perioder:
    def __init__(
        self,
        patterns: Union[str, dict, list],
        log_path: Union[str, Path] = None,
        clock_precision: float = 0.25,
        verbose: bool = True,
    ):
        self.patterns = patterns
        self.log_path = log_path
        self.clock_precision = clock_precision
        self.verbose = verbose
        self.seeker = PatternedDatetimeSeeker(patterns)
        self.bar = TCLogbar()

    def bind(self, func: callable, desc_func: callable = None):
        self.func = func
        self.desc_func = desc_func
        self.file_logger = FileLogger(self.log_path or f"{self.func.__name__}.log")

    def run(self):
        for run_dt_str, remain_seconds in self.seeker:
            remain_seconds_str = logstr.file(f"{remain_seconds}s")
            remain_dt_str = logstr.file(dt_to_str(int(remain_seconds)))
            msg = (
                f"now: {logstr.file(brk(get_now_str()))}, "
                f"next_run: {logstr.file(brk(run_dt_str))}, "
                f"wait_for: {remain_seconds_str} ({remain_dt_str})"
            )
            logger.note(msg, verbose=self.verbose)
            self.file_logger.log(decolored(msg), msg_type="note", add_now=False)
            total = int(remain_seconds)
            run_dt_ts = str_to_ts(run_dt_str)
            self.bar.total = total
            if self.desc_func and callable(self.desc_func):
                self.bar.head = self.desc_func(run_dt_str)
            self.bar.head = logstr.note(self.bar.head or self.func.__name__)
            while remain_seconds > 2 * self.clock_precision:
                now_ts = datetime.now().timestamp()
                self.bar.update(
                    count=round(total - remain_seconds),
                    remain_seconds=round(remain_seconds),
                )
                if now_ts >= run_dt_ts:
                    break
                remain_seconds = run_dt_ts - now_ts
                time.sleep(self.clock_precision)
            self.bar.update(count=total, remain_seconds=0, flush=True)
            self.bar.reset(linebreak=True)
            time.sleep(max(run_dt_ts - datetime.now().timestamp(), 0))
            self.file_logger.log(
                f"Start : {get_now_str()}", msg_type="note", add_now=False
            )
            self.func()
            self.file_logger.log(
                f"Finish: {get_now_str()}", msg_type="success", add_now=False
            )


def foo():
    cmd = 'date +"%T.%N"'
    shell_cmd(cmd, showcmd=False)


def test_perioder():
    logger.note("> test_perioder")
    # patterns = "****-**-** **:**:**"
    patterns = {"second": "*[05]"}
    perioder = Perioder(patterns)
    perioder.bind(foo, desc_func=lambda x: f"foo at {x}")
    perioder.run()


if __name__ == "__main__":
    with Runtimer():
        test_perioder()

    # python -m acto.periods
