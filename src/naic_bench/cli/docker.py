from rich import print as print
from argparse import ArgumentParser
import logging
from logging import getLogger

import os

from naic_bench.cli.base import BaseParser
from naic_bench.docker import Docker

logger = getLogger(__name__)
logger.setLevel(logging.INFO)


class DockerParser(BaseParser):
    def __init__(self, parser: ArgumentParser):
        super().__init__(parser=parser)

        parser.add_argument("--rebuild", action="store_true", default=False)
        parser.add_argument("--restart", action="store_true", default=False)

        parser.add_argument("--device-type", required=True, type=str, default=None)
        parser.add_argument("--container",
            help="The container name, default is 'naic-bench-<device-type>'",
            required=False,
            type=str,
            default=None
        )
        parser.add_argument("--data-dir", type=str, default=None)

        parser.add_argument("--cpus", type=int, default=os.cpu_count())
        parser.add_argument("--shm-size", type=str, default="16g")

    def execute(self, args, options):
        super().execute(args, options)

        exec_args = options
        if options and options[0] == "--":
            exec_args = options[1:]

        Docker.run(
             device_type=args.device_type,
             container_name=args.container,
             rebuild=args.rebuild,
             restart=args.restart,
             data_dir=args.data_dir,
             cpus=args.cpus,
             shm_size=args.shm_size,
             exec_args=exec_args)
