from tclogger import shell_cmd, logger, get_now_str

from acto.periods import Perioder
from acto.retry import Retrier, SoftRetrier


def foo():
    cmd = 'date +"%T.%N"'
    shell_cmd(cmd, showcmd=False)


def foo_desc_func(x):
    func_strs = ['date +"%T.%N"']
    desc_str = f"foo at {x}"
    return func_strs, desc_str


def test_perioder():
    logger.note("> test_perioder")
    # patterns = "****-**-** **:**:**"
    patterns = {"second": "*[05]"}
    perioder = Perioder(patterns)
    perioder.bind(func=foo, desc_func=foo_desc_func)
    perioder.run()


foo_call_count = 0


def foo_to_retry(ok_until: int = 3):
    global foo_call_count
    foo_call_count += 1

    if foo_call_count < ok_until:
        raise RuntimeError(f"foo_to_retry failed at call: {foo_call_count}")
    else:
        cmd = 'date +"%T.%N"'
        shell_cmd(cmd, showcmd=False)


def test_retrier():
    logger.note("> test_retrier")
    with Retrier(max_retries=3, retry_interval=0.5) as retrier:
        retrier.run(foo_to_retry, ok_until=4)
    logger.mesg("* test_retrier completed")


bar_call_count = 0


def bar_to_soft_retry(ok_until: int = 3):
    global bar_call_count
    bar_call_count += 1
    if bar_call_count < ok_until:
        return False
    else:
        cmd = 'date +"%T.%N"'
        shell_cmd(cmd, showcmd=False)
        print(f"Good at call: {bar_call_count}")
        return True


def test_soft_retrier():
    logger.note("> test_soft_retrier")
    with SoftRetrier(max_retries=3, retry_interval=0.5) as retrier:
        retrier.run(bar_to_soft_retry, ok_until=4)
    logger.mesg("* test_soft_retrier completed")


if __name__ == "__main__":
    # test_perioder()
    # test_retrier()
    test_soft_retrier()

    # python -m acto.tests
