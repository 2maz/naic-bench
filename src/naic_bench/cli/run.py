from argparse import ArgumentParser
import logging

from naic_bench.cli.base import BaseParser
from naic_bench.run import BenchmarkRunner

logger = logging.getLogger(__name__)

class RunParser(BaseParser):
    def __init__(self, parser: ArgumentParser):
        super().__init__(parser=parser)

        parser.add_argument("--data-dir", required=True, default=None, type=str)
        parser.add_argument("--benchmarks-dir", required=True, default=None, type=str)

        parser.add_argument("--framework", default="pytorch", type=str)
        parser.add_argument("--benchmark", required=True, type=str)
        parser.add_argument("--variant", required=True, type=str)
        parser.add_argument("--device-type", required=True, type=str)

        parser.add_argument("--confd-dir", default=None, type=str)
        parser.add_argument("--gpu-count", type=int, default=1)

    def execute(self, args):
        super().execute(args)

        runner = BenchmarkRunner(
                data_dir=args.data_dir,
                benchmarks_dir=args.benchmarks_dir,
                confd_dir=args.confd_dir
        )

        report = runner.execute(args.framework,
                args.benchmark, args.variant,
                device_type=args.device_type,
                gpu_count=args.gpu_count
        )
        print(report)
