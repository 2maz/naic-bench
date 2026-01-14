from pathlib import Path
import subprocess
import logging
import os

from naic_bench.spec import BenchmarkSpec
from naic_bench.package_manager import PackageManagerFactory

logger = logging.getLogger(__name__)

# Define apt packages
PREREQUISITES = {
    'apt': [
        "curl",
        "g++",
        "git",
        "python3",
        "python3-dev",
        "python3-venv",
        "unzip",
        "wget"
    ],
    'dnf': [
        "curl",
        "g++",
        "git",
        "python3",
        "python3-devel",
        "python3-venv"
        "unzip",
        "wget"
    ]
}

class BenchmarkPrepare:
    data_dir: Path
    benchmarks_dir: Path
    confd_dir: Path

    def __init__(self, *,
            data_dir: Path | str,
            benchmarks_dir: Path | str,
            confd_dir: Path | str
            ):
        self.data_dir = Path(data_dir).resolve()
        self.benchmarks_dir = Path(benchmarks_dir).resolve()
        self.confd_dir = Path(confd_dir).resolve()

    @classmethod
    def install_prerequisites(cls):
        package_manager = PackageManagerFactory.get_instance()
        package_manager.ensure_packages(PREREQUISITES)

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

                    if not self.benchmarks_dir.exists():
                        logger.info("Cloning: {benchmark_spec.repo.url} branch={benchmark_spec.repo.branch} into {self.benchmarks_dir}")
                        Repo.clone_from(benchmark_spec.repo.url,
                                        branch=benchmark_spec.repo.branch,
                                        to_path=self.benchmarks_dir)

                    env = os.environ.copy()
                    env['DATA_DIR'] = benchmark_spec.data_dir
                    env['TMP_DIR'] = benchmark_spec.temp_dir
                    env['BENCHMARK_DIR'] = Path(self.benchmarks_dir) / benchmark_spec.base_dir

                    subprocess.run([prepare_file, self.data_dir, self.benchmarks_dir], env=env)
                    mark_as_run.add(prepare_file)
