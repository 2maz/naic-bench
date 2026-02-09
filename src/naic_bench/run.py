from rich import print as print
from pathlib import Path
import subprocess
import logging
import shutil
import yaml
import time
import os
import platform
import psutil
import signal
import site
from slurm_monitor.utils.system_info import SystemInfo

from naic_bench.utils import Command, find_confd
from naic_bench.spec import (
        VirtualEnv,
        Report,
        BenchmarkSpec
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class BenchmarkRunner:
    benchmark_specs: dict[str, any]

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

        if confd_dir is None:
            confd_dir = find_confd()

        self.confd_dir = Path(confd_dir).resolve()
        if not self.confd_dir.exists():
            raise RuntimeError(f"Could not find confd directory: {self.confd_dir}")

        self.benchmark_specs = {}

        self.load_all()

    def prepare_venv(self, benchmark_name: str, benchmark_dir: Path | str, work_dir: Path | str = Path().resolve(), force: bool = False) -> str:
        """
        Prepare venv and return python path setting
        """
        venv_path = (work_dir / f"venv-{benchmark_name}-{platform.machine()}").resolve()

        # plain execution of the benchmark
        result = subprocess.run(["which", "python"], stdout=subprocess.PIPE)
        python_path = result.stdout.decode("UTF-8").strip()
        version = '.'.join(platform.python_version_tuple()[:2])
        site_packages = "lib/python" + version + "/site-packages"

        python_site_packages = python_path.replace(r"bin/python", site_packages)
        python_path = f"{Path(venv_path).resolve()}/{site_packages}:{python_site_packages}"

        python_path = f"{python_path}:{':'.join(site.getsitepackages())}"
        venv = VirtualEnv(path=venv_path, python_path=python_path)

        if venv.path.exists():
            if force:
                logger.warning(f"BenchmarkRunner[{benchmark_name}]: venv: {venv.name} already exists (forcing recreation)")
                shutil.rmtree(venv.path)
            else:
                logger.info(f"BenchmarkRunner[{benchmark_name}]: venv: {venv.name} already exists (reusing)")
                return venv

        if not venv.path.exists():
            logger.info(f"BenchmarkRunner[{benchmark_name}]: preparing venv: {venv.name}")
            result = subprocess.run(["python3", "-m", "venv", venv.path],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
            if result.returncode != 0:
                raise RuntimeError(f"BenchmarkRunner[{benchmark_name}]: preparing venv: {venv.name} failed")

            requirements_txt = benchmark_dir / "requirements.txt"
            if requirements_txt.exists():
                subprocess.run(f". {venv.path}/bin/activate; PYTHONPATH={venv.python_path} pip install -r {requirements_txt}", shell=True)
        return venv

    def load_all(self):
        self.benchmark_specs = BenchmarkSpec.load_all(confd_dir=self.confd_dir, data_dir=self.data_dir)


    def execute_all(self,
            framework: str,
            names: list[str] = [],
            variants: list[str] = [],
            device_type: str = "cpu",
            gpu_count: int = 1,
            cpu_count: int | None = None,
            timeout_in_s: int = 3600,
            grace_period_in_s: int = 30,
            recreate_venv: bool = False):

        benchmarks = BenchmarkSpec.all_as_list(confd_dir=self.confd_dir, data_dir=self.data_dir)
        reports = []

        if not names:
            all_benchmarks = [y for x,y,z,spec in benchmarks]
            msg = f"Running all benchmarks defined in {self.confd_dir}\n{sorted(all_benchmarks)}"
            if variants:
                msg += "(for variants: {variants})"
            else:
                msg += "(for all variants)"
            print(msg)

        for framework, benchmark_name, variant, benchmark_spec in benchmarks:
            if names and benchmark_name not in names:
                continue

            if variants and variant not in variants:
                continue

            report = self.execute(framework=framework,
                    name=benchmark_name,
                    variant=variant,
                    device_type=device_type,
                    gpu_count=gpu_count,
                    cpu_count=cpu_count,
                    timeout_in_s=timeout_in_s,
                    recreate_venv=recreate_venv
            )
            reports.append(report)
            print(f"BenchmarkRunner {benchmark_name}|{variant}: Grace period: waiting to {grace_period_in_s} s to finalize")
            for i in reversed(range(0, grace_period_in_s)):
                print(".", end='')
                time.sleep(1)
            print(f"BenchmarkRunner {benchmark_name}|{variant}: Grace period: completed")
        return reports

    def execute(self,
            framework: str,
            name: str,
            variant: str,
            device_type: str = "cpu",
            gpu_count: int = 1,
            cpu_count: int | None = None,
            timeout_in_s: int = 3600,
            recreate_venv: bool = False):
        config = self.benchmark_specs[framework][name][variant]
        config.expand_placeholders(GPU_COUNT=gpu_count)
        if cpu_count is None:
            cpu_count = os.cpu_count()

        config.expand_placeholders(CPU_COUNT=cpu_count)

        clone_target_path = config.git_target_dir(self.benchmarks_dir)
        benchmark_dir = clone_target_path / config.base_dir

        cmd = config.get_command(device_type=device_type, gpu_count=gpu_count)
        logger.info(f"Execute: {cmd} in {benchmark_dir=}")

        venv = self.prepare_venv(benchmark_name=name, benchmark_dir=benchmark_dir, force=recreate_venv)

        logger.info(f"BenchmarkRunner.execute [{name}|{variant=}]: . {venv.name}/bin/activate; cd {benchmark_dir}; PYTHONPATH={venv.python_path} {cmd}")
        result = Command.run_with_progress(
                    [f". {venv.path}/bin/activate; cd {benchmark_dir}; PYTHONPATH={venv.python_path} timeout {timeout_in_s}s {cmd}"],
                    shell=True,
                    raise_on_error=False
                 )
        try:
            psutil.Process(result.pid)
            logger.info(f"BenchmarkRunner.execute [{name}|{variant=}]: process {result.pid} is still running - trying to kill")
            os.kill(result.pid, signal.SIGKILL)
        except psutil.NoSuchProcess:
            # this is how
            pass
        except OSError:
            logger.info(f"BenchmarkRunner.execute [{name}|{variant=}]: failed to kill process {result.pid}")

        with open(config.temp_dir / "stdout.log", "w") as f:
            for line in result.stdout:
                f.write(f"{line}\n")

        with open(config.temp_dir / "stderr.log", "w") as f:
            for line in result.stderr:
                f.write(f"{line}\n")

        si = SystemInfo()

        with open(config.temp_dir / "system_info.yaml", "w") as f:
            data = dict(si)

            try:
                import torch
                data['software'] = { 'torch': torch.__version__ }
            except ImportError:
                logger.warning("BenchmarkRunner: failed to check torch version")

            yaml.dump(data, f)

        metrics = {}
        if result.returncode == 0:
            metrics = config.extract_metrics(result.stdout + result.stderr)

        report = Report(
            benchmark=name,
            variant=variant,
            start_time=int(result.start_time.timestamp()),
            end_time=int(result.end_time.timestamp()),
            exit_code=result.returncode,
            # slurm_job_id=0
            device_type=device_type,
            gpu_model=si.gpu_info.model,
            gpu_count=gpu_count,
            metrics=metrics
        )

        with open(config.temp_dir / "report.yaml", "w") as f:
            yaml.dump(report.model_dump(), f)

        return report
