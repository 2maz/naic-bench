from argparse import ArgumentParser
import logging

from naic_bench.cli.base import BaseParser
from naic_bench.prepare import BenchmarkPrepare

logger = logging.getLogger(__name__)

class PrepareParser(BaseParser):
    def __init__(self, parser: ArgumentParser):
        super().__init__(parser=parser)

        parser.add_argument("--data-dir", required=True, default=None, type=str)
        parser.add_argument("--benchmarks-dir", required=True, default=None, type=str)
        parser.add_argument("--confd-dir", default=None, type=str)

        parser.add_argument("--benchmark",
                nargs="+",
                type=str,
                default=None,
                help="Benchmark name(s)"
        )

    def execute(self, args):
        super().execute(args)

        bp = BenchmarkPrepare(data_dir=args.data_dir,
                benchmarks_dir=args.benchmarks_dir,
                confd_dir=args.confd_dir)

        bp.install_prerequisites()

        bp.prepare(args.benchmark)
