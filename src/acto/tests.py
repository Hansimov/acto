from tclogger import shell_cmd, logger, get_now_str
from acto.periods import Perioder
from acto.retry import Retrier


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


if __name__ == "__main__":
    # test_perioder()
    test_retrier()

    # python -m acto.tests
