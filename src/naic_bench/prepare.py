from pathlib import Path
import subprocess
import logging
import os

from naic_bench.utils import run_command
from naic_bench.spec import BenchmarkSpec

logger = logging.getLogger(__name__)

PREREQUISITES = [
    "curl",
    "git",
    "python3",
    "unzip",
    "wget"
]

class BenchmarkPrepare:
    data_dir: Path
    benchmarks_dir: Path
    confd_dir: Path

    def __init__(self, *,
            data_dir: Path | str,
            benchmarks_dir: Path | str,
            confd_dir: Path | str
            ):
        self.data_dir = Path(data_dir)
        self.benchmarks_dir = Path(benchmarks_dir)
        self.confd_dir = Path(confd_dir)

    @classmethod
    def install_prerequisites(cls):
        install_pkgs = []
        for pkg in PREREQUISITES:
            cmd = [ "dpkg-query", "-W", "-f='${Status}'", pkg ]
            result = run_command(cmd, requires_root=False)
            if "install ok installed" not in result:
                install_pkgs.append(pkg)

        cmd = [ "python3", "-m", "venv", "--help" ]
        result = run_command(cmd, requires_root=False)
        if not result.startswith("usage"):
            install_pkgs.append("python3-venv")

        if install_pkgs:
            env = { "DEBIAN_FRONTEND": "noninteractive" }

            cmd = ["apt", "update"]
            result = run_command(cmd, env=env)

            cmd = ["apt", "install", "-y", "--quiet"] + install_pkgs
            result = run_command(cmd, env=env)

    def prepare(self, benchmark_names: list[str] | None = None):
        benchmarks = BenchmarkSpec.all_as_list(confd_dir=self.confd_dir, data_dir=self.data_dir)
        mark_as_run = set()
        for framework, benchmark_name, variant, benchmark_spec in benchmarks:
            if benchmark_names and benchmark_name not in benchmark_names:
                continue

            logger.info(f"{framework=} {benchmark_name=} {variant=}")
            for category, prepare_scripts in benchmark_spec.prepare.items():
                for prepare_file in prepare_scripts:
                    if not Path(prepare_file).is_absolute():
                        prepare_file = Path(self.confd_dir) / prepare_file

                    prepare_file = prepare_file.resolve()
                    if prepare_file in mark_as_run:
                        continue

                    logger.info(f"BenchmarkPrepare [{category}]: {framework=} {benchmark_name=} -  {prepare_file} {self.data_dir} {self.benchmarks_dir}")

                    env = os.environ.copy()
                    env['DATA_DIR'] = benchmark_spec.data_dir
                    env['TMP_DIR'] = benchmark_spec.temp_dir
                    env['BENCHMARK_DIR'] = Path(self.benchmarks_dir) / benchmark_spec.base_dir

                    subprocess.run([prepare_file, self.data_dir, self.benchmarks_dir], env=env)
                    mark_as_run.add(prepare_file)
