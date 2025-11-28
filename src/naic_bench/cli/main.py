from argparse import ArgumentParser
import sys
import traceback as tb
import logging
from logging import basicConfig, getLogger

from naic_bench.cli.base import BaseParser
from naic_bench.cli.prepare import PrepareParser
from naic_bench.cli.run import RunParser

from naic_bench import __version__

logger = getLogger(__name__)
logger.setLevel(logging.INFO)

class MainParser(ArgumentParser):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.description = "naic-bench - benchmarking GPU-based system"
        self.add_argument("--log-level", type=str, default="INFO", help="Logging level")
        self.add_argument("--version", "-i", action="store_true", help="Show version")

    def attach_subcommand_parser(
        self, subcommand: str, help: str, parser_klass: BaseParser
    ):
        if not hasattr(self, 'subparsers'):
            # lazy initialization, since it cannot be part of the __init__ function
            # otherwise random errors
            self.subparsers = self.add_subparsers(help="sub-command help")

        subparser = self.subparsers.add_parser(subcommand)
        parser_klass(parser=subparser)

def run():
    basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    main_parser = MainParser()

    main_parser.attach_subcommand_parser(
        subcommand="prepare",
        help="Prepare benchmarks, e.g., downloading data and setting up venvs",
        parser_klass=PrepareParser
    )

    main_parser.attach_subcommand_parser(
        subcommand="run",
        help="Run benchmarks",
        parser_klass=RunParser
    )

    args = main_parser.parse_args()

    if args.version:
        print(__version__)
        sys.exit(0)

    if hasattr(args, "active_subparser"):
        try:
            getattr(args, "active_subparser").execute(args)
        except Exception as e:
            tb.print_tb(e.__traceback__)
            print(f"Error: {e}")
            sys.exit(-1)
    else:
        main_parser.print_help()

    for logger in [logging.getLogger(x) for x in logging.root.manager.loggerDict]:
        logger.setLevel(logging.getLevelName(args.log_level))

if __name__ == "__main__":
    run()
