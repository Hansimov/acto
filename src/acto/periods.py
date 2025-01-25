import re

from collections.abc import Generator
from datetime import datetime
from itertools import product
from tclogger import logger, logstr, Runtimer
from tclogger import get_now, get_now_str, str_to_ts, t_to_str, str_to_ts, str_to_t
from typing import Union, Literal

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

ISO-format str:
    - 'YYYY-mm-dd HH:MM:SS'
    - 'mm-dd HH:MM:SS'
    - 'YYYY-mm-dd'
    - 'mm-dd'
    - 'HH:MM:SS'
    ' 'MM:SS'
"""

FULL_ISO_MASK = "****-**-** **:**:**"
FULL_ISO_ZERO = "0000-00-00 00:00:00"


def is_dt_str_full_iso(dt_str: str) -> bool:
    return len(dt_str) == len(FULL_ISO_MASK)


def mask_dt_str(
    dt_str: str,
    lmask: str = FULL_ISO_MASK,
    rmask: str = FULL_ISO_ZERO,
    start: int = None,
    end: int = None,
) -> str:
    if start is None:
        start = 0
    if end is None:
        end = len(dt_str)
    return lmask[:start] + dt_str + rmask[end:]


def fill_iso(
    dt_str: str,
    lmask: str = FULL_ISO_MASK,
    rmask: str = FULL_ISO_ZERO,
) -> str:
    dt_len = len(dt_str)
    full_len = len(FULL_ISO_MASK)
    if dt_len == full_len:
        return dt_str
    masked_str = re.sub(r"\d", "*", dt_str)
    # slide window from right to left
    for i in range(full_len - dt_len):
        end = full_len - i
        start = end - dt_len
        if FULL_ISO_MASK[start:end] == masked_str:
            return lmask[:start] + dt_str + rmask[end:]
    raise ValueError(f"× Cannot fill ISO format: {dt_str}")


def is_dt_str_valid(dt_str: str) -> bool:
    try:
        str_to_ts(dt_str)
        return True
    except:
        return False


def is_dt_str_later_equal(dt_str1: str, dt_str2: str) -> bool:
    return str_to_ts(dt_str1) >= str_to_ts(dt_str2)


def is_dt_str_later(dt_str1: str, dt_str2: str) -> bool:
    return str_to_ts(dt_str1) > str_to_ts(dt_str2)


def is_dt_str_valid_and_later(dt_str: str, dt_beg: str) -> bool:
    return is_dt_str_valid(dt_str) and is_dt_str_later(dt_str, dt_beg)


def dt_pattern_to_regex(pattern: str) -> tuple:
    ymdh_list = re.findall(r"[\d\*]+", pattern)
    yyyy, mm, dd, hh, mi, ss = list(map(lambda x: x.replace("*", "\d"), ymdh_list))
    return yyyy, mm, dd, hh, mi, ss


def re_match_nn(re_pattern: str, num: Union[int, str], digits: int = 2) -> bool:
    return re.match(re_pattern, f"{num:0{digits}d}")


def unify_dt_beg_end(
    dt_be: str = None, pos: Literal["beg", "end"] = "beg"
) -> tuple[str, datetime]:
    if pos == "beg":
        bound_str = get_now_str()
    else:
        bound_str = "9999-12-31 23:59:59"
    if dt_be is None:
        dt_be = bound_str
    else:
        dt_be = fill_iso(dt_be, lmask=bound_str, rmask=bound_str)
    t_be = str_to_t(dt_be)
    return dt_be, t_be


def zip_kvs(keys: Union[list[str], str], vals: Union[list[str], str]) -> dict:
    if isinstance(keys, (list, tuple)) and isinstance(vals, (list, tuple)):
        return dict(zip(keys, vals))
    key = keys[0] if isinstance(keys, (list, tuple)) else keys
    val = vals[0] if isinstance(vals, (list, tuple)) else vals
    return {key: val}


def tuplize_vars(v1: Union[tuple, str, int], v2: Union[tuple, str, int]) -> tuple:
    if isinstance(v1, (str, int)):
        v1 = (v1,)
    if isinstance(v2, (str, int)):
        v2 = (v2,)
    return v1 + v2


class PatternedDatetimeSeeker:
    DD_RANGES = {
        "month": range(1, 13),
        "month_r": range(12, 0, -1),
        "day": range(1, 32),
        "day_r": range(31, 0, -1),
        "hour": range(0, 24),
        "hour_r": range(23, -1, -1),
        "minute": range(0, 60),
        "minute_r": range(59, -1, -1),
        "second": range(0, 60),
        "second_r": range(59, -1, -1),
    }
    DD_ATTRS = {
        "year": "yyyy",
        "month": "mm",
        "day": "dd",
        "hour": "hh",
        "minute": "mi",
        "second": "ss",
    }

    def __init__(self, pattern: str, dt_beg: str = None, dt_end: str = None) -> None:
        self.min_year = None
        self.min_month = None
        self.min_day = None
        self.min_hour = None
        self.min_minute = None
        self.min_second = None
        self.dt_beg = dt_beg
        self.dt_end = dt_end
        self.pattern = pattern

    def update_dt_beg_end(self) -> tuple[str, str]:
        self.dt_beg, self.t_beg = unify_dt_beg_end(self.dt_beg, "beg")
        self.DD_RANGES["year"] = range(self.t_beg.year, 9999)

    def update_ymdhms_pattern(self, pattern: str = None) -> str:
        if not pattern:
            pattern = self.pattern
        regex_res = dt_pattern_to_regex(pattern)
        self.yyyy, self.mm, self.dd, self.hh, self.mi, self.ss = regex_res

    def iter_dd(self, level: str) -> Generator[str, None, None]:
        attr = self.DD_ATTRS[level.split("_")[0]]
        dd_range = self.DD_RANGES[level]
        pattern = getattr(self, attr)
        for dd in dd_range:
            if re_match_nn(pattern, dd):
                yield dd

    def iter_dds_product(self, levels: list[str]) -> Generator[tuple[str], None, None]:
        for dds in product(*[self.iter_dd(level) for level in levels]):
            yield dds

    def is_ymdhms_valid_and_later(
        self,
        year: int = None,
        month: int = None,
        day: int = None,
        hour: int = None,
        minute: int = None,
        second: int = None,
        day_end: bool = False,
    ) -> bool:
        yy = f"{year:04d}" if year is not None else self.min_year
        mm = f"{month:02d}" if month is not None else self.min_month
        dd = f"{day:02d}" if day is not None else self.min_day
        hh = f"{hour:02d}" if hour is not None else ("23" if day_end else self.min_hour)
        mi = (
            f"{minute:02d}"
            if minute is not None
            else ("59" if day_end else self.min_minute)
        )
        ss = (
            f"{second:02d}"
            if second is not None
            else ("59" if day_end else self.min_second)
        )
        dt_str = f"{yy}-{mm}-{dd} {hh}:{mi}:{ss}"
        return is_dt_str_valid_and_later(dt_str, self.dt_beg)

    def iter_dds_product_and_check(
        self,
        levels: list[str],
        dd_type: Literal["ymd", "hms"] = "ymd",
        extra_level_kvs: dict = {},
    ) -> Generator[tuple[str], None, None]:
        level_keys = [level.split("_")[0] for level in levels]
        if len(levels) == 1:
            product_iter = self.iter_dd(levels[0])
        else:
            product_iter = self.iter_dds_product(levels)
        for dd in product_iter:
            if self.is_ymdhms_valid_and_later(
                **zip_kvs(level_keys, dd), **extra_level_kvs, day_end=(dd_type == "ymd")
            ):
                yield dd

    def double_iter_dds_product_and_check(
        self, ymd_levels: list[str], hms_levels: list[str]
    ) -> Generator[tuple[str], None, None]:
        ymd_level_keys = [level.split("_")[0] for level in ymd_levels]
        for ymd in self.iter_dds_product_and_check(ymd_levels, "ymd"):
            for hms in self.iter_dds_product_and_check(
                hms_levels, "hms", extra_level_kvs=zip_kvs(ymd_level_keys, ymd)
            ):
                yield tuplize_vars(ymd, hms)

    def calc_min_matched_year(self) -> str:
        for year, *_ in self.double_iter_dds_product_and_check(
            ["year", "month_r", "day_r"], ["hour_r", "minute_r", "second_r"]
        ):
            min_year = f"{year:04d}"
            self.min_year = min_year
            return min_year

    def calc_min_matched_month(self) -> str:
        for month, *_ in self.double_iter_dds_product_and_check(
            ["month", "day_r"], ["hour_r", "minute_r", "second_r"]
        ):
            self.min_month = f"{month:02d}"
            return self.min_month

    def calc_min_matched_day(self) -> str:
        for day, *_ in self.double_iter_dds_product_and_check(
            ["day"], ["hour_r", "minute_r", "second_r"]
        ):
            self.min_day = f"{day:02d}"
            return self.min_day

    def calc_min_matched_hour(self) -> str:
        for hour, *_ in self.double_iter_dds_product_and_check(
            ["hour"], ["minute_r", "second_r"]
        ):
            self.min_hour = f"{hour:02d}"
            return self.min_hour

    def calc_min_matched_minute(self) -> str:
        for minute, *_ in self.double_iter_dds_product_and_check(
            ["minute"], ["second_r"]
        ):
            self.min_minute = f"{minute:02d}"
            return self.min_minute

    def calc_min_matched_second(self) -> str:
        for second in self.iter_dds_product_and_check(["second"], "hms"):
            self.min_second = f"{second:02d}"
            return self.min_second

    def get_min_matched_dt_str(self) -> str:
        self.update_dt_beg_end()
        self.update_ymdhms_pattern()
        self.calc_min_matched_year()
        self.calc_min_matched_month()
        self.calc_min_matched_day()
        self.calc_min_matched_hour()
        self.calc_min_matched_minute()
        self.calc_min_matched_second()
        return f"{self.min_year}-{self.min_month}-{self.min_day} {self.min_hour}:{self.min_minute}:{self.min_second}"


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


def test_fill_iso():
    logger.note("> test_fill_iso")
    dt_strs = ["00:30", "00:30:", "12-31", "12:00:00", "1 12", "01 **:00:00"]
    with logger.temp_indent(2):
        for dt_str in dt_strs:
            logger.mesg(fill_iso(dt_str))
        now_str = get_now_str()
        for dt_str in dt_strs:
            logger.file(fill_iso(dt_str, lmask=now_str))


def test_get_min_matched_dt_str():
    logger.note("> test_get_min_matched_dt_str")
    pattern_answers = [
        ("****-**-** **:**:**", "2025-01-25 02:58:31", "2025-01-25 02:58:32"),
        ("****-**-** 01:**:**", "2025-12-30 00:00:00", "2025-12-30 01:00:00"),
        ("****-**-** 00:**:**", "2025-12-31 23:00:00", "2026-01-01 00:00:00"),
        ("****-*3-** *1:3*:**", "2025-04-30 00:00:00", "2026-03-01 01:30:00"),
        ("****-*3-** *5:**:**", "2022-04-30 00:00:00", "2023-03-01 05:00:00"),
        ("****-*3-** *5:2*:**", "2022-04-30 00:00:00", "2023-03-01 05:20:00"),
        ("****-*2-** 00:00:00", "2024-02-28 00:00:00", "2024-02-29 00:00:00"),
        ("****-*2-** 00:00:00", "2025-02-28 00:00:00", "2025-12-01 00:00:00"),
        ("****-02-** 00:00:00", "2025-02-28 00:00:00", "2026-02-01 00:00:00"),
        ("****-**-*1 00:00:00", "2025-02-28 00:00:00", "2025-03-01 00:00:00"),
    ]
    with logger.temp_indent(2):
        for pattern, dt_beg, answer in pattern_answers:
            matcher = PatternedDatetimeSeeker(pattern, dt_beg)
            res = matcher.get_min_matched_dt_str()
            # matcher.dt_beg = res
            # res = matcher.get_min_matched_dt_str()
            if res == answer:
                mark = logstr.success("✓")
                answer_str = logstr.success(answer)
            else:
                mark = logstr.warn("×")
                answer_str = f"{logstr.warn(res)} ≠ {logstr.success(answer)}"
            dt_beg_str = logstr.file(f"(after {dt_beg})")
            logger.mesg(f"{mark} {pattern} {dt_beg_str} → {answer_str}")


if __name__ == "__main__":
    with Runtimer():
        # test_fill_iso()
        test_get_min_matched_dt_str()

    # python -m acto.periods
