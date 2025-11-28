from pathlib import Path
import subprocess
import logging
import yaml
import os
import platform
import site
import selectors
import sys
import time
import datetime as dt

from slurm_monitor.utils.system_info import SystemInfo

from naic_bench.utils import pipe_has_data
from naic_bench.spec import (
        VirtualEnv,
        Report,
        BenchmarkSpec
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class BenchmarkRunner:
    benchmark_specs: dict[str, any]

    def __init__(self, *,
            data_dir: Path | str,
            benchmarks_dir: Path | str,
            confd_dir: Path | str
            ):
        self.data_dir = Path(data_dir)
        self.benchmarks_dir = Path(benchmarks_dir)
        self.confd_dir = Path(confd_dir)

        self.benchmark_specs = {}

        self.load_all()

    def prepare_venv(self, benchmark_name: str, workdir: Path | str) -> str:
        """
        Prepare venv and return python path setting
        """
        venv_name = f"venv-{benchmark_name}-{platform.machine()}"

        # plain execution of the benchmark
        result = subprocess.run(["which", "python"], stdout=subprocess.PIPE)
        python_path = result.stdout.decode("UTF-8").strip()
        version = '.'.join(platform.python_version_tuple()[:2])
        site_packages = "lib/python" + version + "/site-packages"

        python_site_packages = python_path.replace(r"bin/python", site_packages)
        python_path = f"{Path(venv_name).resolve()}/{site_packages}:{python_site_packages}"

        python_path = f"{python_path}:{':'.join(site.getsitepackages())}"
        venv = VirtualEnv(name=venv_name, python_path=python_path)

        if not Path(venv_name).exists():
            logger.info(f"BenchmarkRunner[{benchmark_name}]: preparing venv: {venv_name}")
            subprocess.run(["python3", "-m", "venv", venv_name],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)

            requirements_txt = workdir / "requirements.txt"
            if requirements_txt.exists():
                subprocess.run(f". {venv_name}/bin/activate; PYTHONPATH={venv.python_path} pip install -r {requirements_txt}", shell=True)
        else:
            logger.info(f"BenchmarkRunner[{benchmark_name}]: venv: {venv_name} already exists")
        return venv

    def load_all(self):
        self.benchmark_specs = BenchmarkSpec.load_all(confd_dir=self.confd_dir, data_dir=self.data_dir)

    def execute(self,
            framework: str,
            name: str,
            variant: str,
            device_type: str = "cpu",
            gpu_count: int = 1,
            timeout_in_s: int = 1200):
        config = self.benchmark_specs[framework][name][variant]
        config.expand_placeholders(GPU_COUNT=gpu_count)

        workdir = self.benchmarks_dir / config.base_dir

        cmd = config.get_command(device_type=device_type, gpu_count=gpu_count)
        logger.info(f"Execute: {cmd} in {workdir}")

        venv = self.prepare_venv(benchmark_name=name, workdir=workdir)

        stdout = []
        stderr = []
        start_time = dt.datetime.now(tz=dt.timezone.utc)
        logger.info(f"BenchmarkRunner.execute [{name}|{variant=}]: . {venv.name}/bin/activate; cd {workdir}; PYTHONPATH={venv.python_path} {cmd}")
        with subprocess.Popen(
                    f". {venv.name}/bin/activate; cd {workdir}; PYTHONPATH={venv.python_path} {cmd}",
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                ) as process:

            os.set_blocking(process.stdout.fileno(), False)
            stdout_selector = selectors.DefaultSelector()
            stdout_selector.register(process.stdout, selectors.EVENT_READ)

            os.set_blocking(process.stderr.fileno(), False)
            stderr_selector = selectors.DefaultSelector()
            stderr_selector.register(process.stderr, selectors.EVENT_READ)

            while process.poll() is None:
                if pipe_has_data(process.stdout, stdout_selector):
                    stdout_line = process.stdout.readline()
                    if stdout_line:
                        output_line = stdout_line.decode("UTF-8").strip()
                        print(output_line, flush=True, file=sys.stdout)
                        stdout.append(output_line)

                if pipe_has_data(process.stderr, stderr_selector):
                    stderr_line = process.stderr.readline()
                    if stderr_line:
                        output_line = stderr_line.decode("UTF-8").strip()
                        print(output_line, flush=True, file=sys.stderr)
                        stderr.append(output_line)

                time.sleep(0.1)

            end_time = dt.datetime.now(tz=dt.timezone.utc)
            # Get remaining lines
            for line in process.stdout:
                output_line = line.decode("UTF-8").strip()
                stdout.append(output_line)
                print(output_line, flush=True, file=sys.stdout)

            for line in process.stderr:
                output_line = line.decode("UTF-8").strip()
                stderr.append(output_line)
                print(output_line, flush=True, file=sys.stderr)

            if process.returncode != 0:
                error_details = '\n'.join(stderr)
                raise RuntimeError(f"Benchmark {name=} {variant=} failed -- details: {error_details}")

        with open(config.temp_dir / "stdout.log", "w") as f:
            for line in stdout:
                f.write(f"{line}\n")

        with open(config.temp_dir / "stderr.log", "w") as f:
            for line in stderr:
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

        report = Report(
            benchmark=name,
            variant=variant,
            start_time=int(start_time.timestamp()),
            end_time=int(end_time.timestamp()),
            # slurm_job_id=0
            device_type=device_type,
            gpu_model=si.gpu_info.model,
            gpu_count=gpu_count,
            metrics=config.extract_metrics(stdout + stderr)
        )

        with open(config.temp_dir / "report.yaml", "w") as f:
            yaml.dump(report.model_dump(), f)

        return report
