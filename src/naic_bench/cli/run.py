from argparse import ArgumentParser
import logging

from naic_bench.cli.base import BaseParser
from naic_bench.run import BenchmarkRunner

import subprocess

logger = logging.getLogger(__name__)

class RunParser(BaseParser):
    def __init__(self, parser: ArgumentParser):
        super().__init__(parser=parser)

        parser.add_argument("--data-dir", required=True, default=None, type=str)
        parser.add_argument("--benchmarks-dir", required=True, default=None, type=str)

        parser.add_argument("--framework", default="pytorch", type=str)
        parser.add_argument("--benchmark",
            nargs="+",
            default=None,
            type=str
        )
        parser.add_argument("--variant",
            nargs="+",
            default=None,
            type=str
        )
        parser.add_argument("--device-type",
                            required=True,
                            help="Device type required: select from 'cpu','cuda','xpu','hpu'",
                            type=str)

        parser.add_argument("--confd-dir", default=None, type=str)
        parser.add_argument("--gpu-count", type=int, default=1)

        parser.add_argument("--recreate-venv",
                            action="store_true",
                            default=False,
                            help="Force the recreation of any related venv for the benchmarks"
        )

    def execute(self, args):
        super().execute(args)

        runner = BenchmarkRunner(
                data_dir=args.data_dir,
                benchmarks_dir=args.benchmarks_dir,
                confd_dir=args.confd_dir
        )

        reports = runner.execute_all(args.framework,
                args.benchmark, args.variant,
                device_type=args.device_type,
                gpu_count=args.gpu_count,
                recreate_venv=args.recreate_venv
        )

        if not reports:
            print("Apparently there was nothing to run. Available benchmarks are:")
            subprocess.run("naic-bench show --compact", shell=True)

        for report in reports:
            print(report)
