from tclogger import shell_cmd, logger, get_now_str
from acto.periods import Perioder


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


if __name__ == "__main__":
    test_perioder()

    # python -m acto.tests
