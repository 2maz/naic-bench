from argparse import ArgumentParser
import logging

from naic_bench.cli.base import BaseParser
from naic_bench.spec import BenchmarkSpec

import re
import json

logger = logging.getLogger(__name__)

class ShowParser(BaseParser):
    def __init__(self, parser: ArgumentParser):
        super().__init__(parser=parser)

        parser.add_argument("--confd-dir", default="./conf.d", type=str)
        parser.add_argument("--data-dir", required=False, default="$NAIC_BENCH_DATA_DIR", type=str)

        parser.add_argument("--benchmark",
            nargs="+",
            type=str,
            help="Name(s) or patterns of benchmarks"
        )

        parser.add_argument("--compact",
            action="store_true",
            default=False,
            help="Print as: <name of benchmark> : <variant>"
        )

    def execute(self, args):
        super().execute(args)

        benchmarks = BenchmarkSpec.all_as_list(
                        confd_dir=args.confd_dir,
                        data_dir=args.data_dir
                    )

        if not args.benchmark:
            benchmarks_pattern = [".*"]
        else:
            benchmarks_pattern = args.benchmark

        for b in benchmarks_pattern:
            pattern = re.compile(f"{b}")

            for framework, benchmark_name, variant, benchmark_spec in benchmarks:
                if pattern.match(benchmark_name):
                    if args.compact:
                        print(f"{benchmark_spec.name}: {benchmark_spec.variant}")
                    else:
                        print(json.dumps(benchmark_spec.model_dump(), indent=4, default=str))
