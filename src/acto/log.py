import json
import threading

from pathlib import Path
from tclogger import logger, get_now_str
from typing import Literal, Union, TypedDict

DURATION_TYPE = Union[int, float, str]


class PeriodInfoCreate(TypedDict):
    cmds: list[str] = None
    run_at: str = None  # time when run starts
    wait_for: DURATION_TYPE = None  # time to wait for run


class PeriodInfoRun(TypedDict):
    cmds: list[str]
    run_at: str = None  # time when run starts
    waited: DURATION_TYPE = None  # time waited after create


class PeriodInfoDone(TypedDict):
    cmds: list[str] = None
    run_at: str = None  # time when run starts
    elapsed: DURATION_TYPE = None  # time elapsed after run


class PeriodMsgType(TypedDict):
    name: str
    now: str
    type: str = "period"
    action: Literal["create", "run", "done"]
    info: Union[PeriodInfoCreate, PeriodInfoRun, PeriodInfoDone]


class ActionLogger:
    def __init__(self, log_path: Union[str, Path], lock: threading.Lock = None):
        self.log_path = Path(log_path)
        self.lock = lock or threading.Lock()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, msg: PeriodMsgType):
        try:
            with open(self.log_path, "r") as f:
                json_data = json.load(f)
        except:
            json_data = []
        json_data.append(msg)
        with self.lock:
            with open(self.log_path, "w") as f:
                json.dump(json_data, f, indent=4)
