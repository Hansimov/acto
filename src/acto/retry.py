from time import sleep
from tclogger import logger, logstr


class Retrier:
    def __init__(self, max_retries: int = 3, retry_interval: float = 2):
        self.max_retries = max_retries
        self.retry_interval = retry_interval
        self.retry_count = 0

    def log_exception(self, exc_type, exc_val):
        err_mesg = f"× Error {exc_type.__name__}: {exc_val}."
        logger.warn(err_mesg)

    def log_retry_next(self):
        retry_count_str = (
            f"[{logstr.file(self.retry_count)}/{logstr.mesg(self.max_retries)}]"
        )
        logger.mesg(f"{retry_count_str} Retry after {self.retry_interval} seconds ...")

    def log_retry_exceed(self):
        logger.warn(f"× Exceed max retries ({self.max_retries}). Exited!")

    def sleep_interval(self):
        sleep(self.retry_interval)

    def is_retry_not_exceeded(self):
        return self.retry_count <= self.max_retries

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def run(self, func, *args, **kwargs):
        while self.is_retry_not_exceeded():
            self.retry_count += 1
            try:
                return func(*args, **kwargs)
            except Exception as e:
                self.log_exception(type(e), e)
                if self.is_retry_not_exceeded():
                    self.log_retry_next()
                    self.sleep_interval()
                else:
                    self.log_retry_exceed()
                    raise e
