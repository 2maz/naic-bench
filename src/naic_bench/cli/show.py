from argparse import ArgumentParser
from rich import print
import logging

from naic_bench.cli.base import BaseParser
from naic_bench.spec import BenchmarkSpec
from naic_bench.utils import find_confd

import re
import json

logger = logging.getLogger(__name__)

class ShowParser(BaseParser):
    def __init__(self, parser: ArgumentParser):
        super().__init__(parser=parser)

        parser.add_argument("--confd-dir", default=None, type=str)
        parser.add_argument("--data-dir", required=False, default="$NAIC_BENCH_DATA_DIR", type=str)

        parser.add_argument("--benchmark",
            nargs="+",
            type=str,
            help="Name(s) or patterns of benchmarks"
        )

        parser.add_argument("--variant",
            nargs="+",
            type=str,
            help="Name(s) or patterns of variants"
        )

        parser.add_argument("--compact",
            action="store_true",
            default=False,
            help="Print as: <name of benchmark> : <variant>"
        )

    def execute(self, args, options):
        super().execute(args, options)

        benchmarks = BenchmarkSpec.all_as_list(
                        confd_dir=find_confd(),
                        data_dir=args.data_dir
                    )

        if not args.benchmark:
            benchmarks_pattern = [".*"]
        else:
            benchmarks_pattern = args.benchmark

        for b in benchmarks_pattern:
            pattern = re.compile(f"{b}")

            for framework, benchmark_name, variant, benchmark_spec in benchmarks:
                if args.variant and variant not in args.variant:
                    continue

                if pattern.match(benchmark_name):
                    if args.compact:
                        prepare_reqs = [f"{x}: {y}" for x, y in benchmark_spec.prepare.items()]
                        print(f"{benchmark_spec.name.ljust(20)}: {benchmark_spec.variant.ljust(10)} <| {','.join(prepare_reqs)}")
                    else:
                        print(json.dumps(benchmark_spec.model_dump(), indent=4, default=str))
