import time

from datetime import datetime
from pathlib import Path
from tclogger import logger, logstr, brk
from tclogger import get_now_str, get_now_ts, str_to_ts, dt_to_str
from tclogger import TCLogbar, add_fills
from typing import Union

from .times import PatternedDatetimeSeeker
from .log import ActionLogger


class Perioder:
    def __init__(
        self,
        patterns: Union[str, dict, list],
        name: str = None,
        log_path: Union[str, Path] = None,
        clock_precision: float = 0.25,
        verbose: bool = True,
    ):
        self.patterns = patterns
        self.log_path = log_path
        self.name = name
        self.clock_precision = clock_precision
        self.verbose = verbose
        self.seeker = PatternedDatetimeSeeker(patterns)
        self.bar = TCLogbar()

    def bind(self, func: callable, desc_func: callable = None):
        self.func = func
        self.desc_func = desc_func
        self.name = self.name or func.__name__
        self.action_logger = ActionLogger(self.log_path or f"{self.func.__name__}.log")

    def log_before_wait(self):
        remain_seconds_str = logstr.file(f"{self.remain_seconds}s")
        remain_dt_str = logstr.file(dt_to_str(int(self.remain_seconds)))
        fill_str = add_fills("", filler="= ")
        create_cli_msg = (
            f"{fill_str}\n"
            f"now: {logstr.file(brk(get_now_str()))}, "
            f"next_run: {logstr.file(brk(self.run_dt_str))}, "
            f"wait_for: {remain_seconds_str} ({remain_dt_str})"
        )
        logger.note(create_cli_msg, verbose=self.verbose)

    def update_desc_and_func(self):
        self.func_strs = []
        self.desc_str = self.func.__name__
        if self.desc_func and callable(self.desc_func):
            self.func_strs, self.desc_str = self.desc_func(self.run_dt_str)

    def action_log_before_wait(self):
        wait_for_str = dt_to_str(int(self.remain_seconds))
        self.create_msg = {
            "name": self.name,
            "now": get_now_str(),
            "type": "period",
            "action": "create",
            "info": {
                "run_at": self.run_dt_str,
                "wait_for": wait_for_str,
                "cmds": self.func_strs,
            },
        }
        self.action_logger.log(self.create_msg)

    def log_wait_progress(self):
        remain_seconds = self.remain_seconds
        total = int(remain_seconds)
        run_dt_ts = str_to_ts(self.run_dt_str)
        self.bar.total = total
        if len(self.desc_str) <= 75:
            self.bar.head = logstr.note(self.desc_str)
        else:
            logger.note(self.desc_str)
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

    def log_before_func(self):
        single_fill_str = add_fills("", filler="- ")
        logger.mesg(single_fill_str, verbose=self.verbose)

    def action_log_before_func(self):
        self.run_msg = {
            "name": self.name,
            "now": get_now_str(),
            "type": "period",
            "action": "run",
            "info": {
                "run_at": self.run_dt_str,
                "cmds": self.func_strs,
            },
        }
        self.action_logger.log(self.run_msg)

    def log_after_func(self):
        pass

    def action_log_after_func(self):
        elapsed_seconds = get_now_ts() - str_to_ts(self.run_dt_str)
        elapsed_str = dt_to_str(elapsed_seconds)
        done_msg = {
            "name": self.name,
            "now": get_now_str(),
            "type": "period",
            "action": "done",
            "info": {
                "run_at": self.run_dt_str,
                "elapsed": elapsed_str,
            },
        }
        self.action_logger.log(done_msg)

    def run(self):
        for run_dt_str, remain_seconds in self.seeker:
            self.run_dt_str = run_dt_str
            self.remain_seconds = remain_seconds
            self.log_before_wait()
            self.update_desc_and_func()
            self.action_log_before_wait()
            self.log_wait_progress()
            self.log_before_func()
            self.action_log_before_func()
            self.func()
            self.log_after_func()
            self.action_log_after_func()
