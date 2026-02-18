from argparse import ArgumentParser
import json
import logging
from pathlib import Path
import yaml

from naic_bench.cli.base import BaseParser
from naic_bench.spec import Report

logger = logging.getLogger(__name__)


class CustomSafeLoader(yaml.SafeLoader):
    def construct_unknown(self, node):
        if node.tag == "!!python/object/new:torch.torch_version.TorchVersion":
            return node.value[0].value

        return None

CustomSafeLoader.add_constructor(None, CustomSafeLoader.construct_unknown)


class ReportParser(BaseParser):
    def __init__(self, parser: ArgumentParser):
        super().__init__(parser=parser)

        parser.add_argument("--output-base-dir",
                            default=None,
                            required=True
        )

        parser.add_argument("--save-as",
                            default="reports.json",
                            help="The export file (either .json or .yaml)"
        )

        parser.add_argument("--benchmark",
                nargs="+",
                type=str,
                default=None,
                help="Benchmark name(s), default is all"
        )

        parser.add_argument("--variant",
                nargs="+",
                type=str,
                default=None,
                help="Benchmark variant name(s), default is all"
        )

        parser.add_argument("--device-type",
                nargs="+",
                type=str,
                default=None,
                help="Device types to take into account, default is all"
        )

    def execute(self, args, options):
        super().execute(args, options)

        reports_search_dir = Path(args.output_base_dir)

        if not reports_search_dir.exists():
            raise FileNotFoundError(f"The directory '{reports_search_dir}' does not exist")

        reports = []
        for benchmark_report in reports_search_dir.glob("*/**/report.yaml"):
            system_info_path = Path(benchmark_report.parent / "system_info.yaml")
            system_info = {}
            if system_info_path.exists():
                with open(system_info_path, "r") as f:
                    system_info = yaml.load(f, Loader=CustomSafeLoader)

            with open(benchmark_report, "r") as f:
                data = yaml.load(f, Loader=yaml.SafeLoader)
                print(Report(**data))
                data['system_info'] = system_info
                reports.append(data)

        with open(args.save_as, "w") as f:
            logger.info(f"Saving reports as {args.save_as}")
            if args.save_as.endswith(".json"):
                json.dump(reports, f)
            elif args.save_as.endswith(".yaml"):
                yaml.dump(reports, f)
            else:
                print("Could not save {args.save_as}. Unknown output format")
