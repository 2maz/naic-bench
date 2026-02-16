from argparse import ArgumentParser
import logging
from logging import basicConfig, getLogger
from rich import print as print
from rich.logging import RichHandler
from rich_argparse import RichHelpFormatter
import sys
import traceback as tb

from naic_bench.cli.base import BaseParser
from naic_bench.cli.docker import DockerParser
from naic_bench.cli.prepare import PrepareParser
from naic_bench.cli.report import ReportParser
from naic_bench.cli.run import RunParser
from naic_bench.cli.show import ShowParser
from naic_bench.cli.singularity import SingularityParser


from naic_bench import __version__

logger = getLogger(__name__)
logger.setLevel(logging.INFO)

class MainParser(ArgumentParser):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.description = "naic-bench - benchmarking GPU-based system"
        self.add_argument("--log-level", type=str, default="INFO", help="Logging level")
        self.add_argument("--version", "-i", action="store_true", help="Show version")
        self.add_argument("--verbose", default=False, action="store_true", help="Show verbose information, including error traceback")

    def attach_subcommand_parser(
        self, subcommand: str, help: str, parser_klass: BaseParser
    ):
        if not hasattr(self, 'subparsers'):
            # lazy initialization, since it cannot be part of the __init__ function
            # otherwise random errors
            self.subparsers = self.add_subparsers(help="sub-command help")

        subparser = self.subparsers.add_parser(subcommand)
        subparser.formatter_class = RichHelpFormatter
        parser_klass(parser=subparser)

def run():
    basicConfig(
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[RichHandler(rich_tracebacks=True)]
    )

    main_parser = MainParser(formatter_class=RichHelpFormatter)

    main_parser.attach_subcommand_parser(
        subcommand="docker",
        help="Prepare and/or use docker image for benchmarking",
        parser_klass=DockerParser
    )

    main_parser.attach_subcommand_parser(
        subcommand="prepare",
        help="Prepare benchmarks, e.g., downloading data and setting up venvs",
        parser_klass=PrepareParser
    )

    main_parser.attach_subcommand_parser(
        subcommand="report",
        help="Report on available benchmark results",
        parser_klass=ReportParser
    )

    main_parser.attach_subcommand_parser(
        subcommand="run",
        help="Run benchmarks",
        parser_klass=RunParser
    )

    main_parser.attach_subcommand_parser(
        subcommand="singularity",
        help="Prepare and/or use singularity image for benchmarking",
        parser_klass=SingularityParser
    )

    main_parser.attach_subcommand_parser(
        subcommand="show",
        help="Show available benchmark specs",
        parser_klass=ShowParser
    )

    args, options = main_parser.parse_known_args()

    if args.version:
        print(__version__)
        sys.exit(0)

    for a_logger in [logging.getLogger(x) for x in logging.root.manager.loggerDict]:
        if a_logger.name.startswith("naic_bench"):
            a_logger.setLevel(logging.getLevelName(args.log_level))

    if hasattr(args, "active_subparser"):
        try:
            getattr(args, "active_subparser").execute(args, options)
        except Exception as e:
            if args.verbose:
                logger.exception(f"Error: {e}")
            else:
                print(f"Error: {e}")
            sys.exit(-1)
    else:
        main_parser.print_help()

if __name__ == "__main__":
    run()
