from abc import ABC, abstractmethod
from naic_bench.utils import Command
from pathlib import Path

import logging

logger = logging.getLogger(__name__)

class PackageManager(ABC):
    @property
    def identifier(self):
        raise RuntimeError("Please implement 'def identifier' for the PackageManager")

    @abstractmethod
    def installed(self, pkg_name: str) -> bool:
        pass

    @abstractmethod
    def update(self) -> bool:
        pass

    @abstractmethod
    def install(self) -> bool:
        pass

    def ensure_packages(self, packages: dict[str, list[str]]) -> bool:
        if self.identifier in packages:
            prerequisites = packages[self.identifier]

            self.install(prerequisites)

class AptPackageManager(PackageManager):
    @property
    def identifier(self):
        return "apt"

    def installed(self, pkg_name: str) -> bool:
        cmd = [ "dpkg-query", "-W", "-f='${Status}'", pkg_name ]
        try:
            result = Command.run(cmd, requires_root=False)
            return "install ok installed" in result
        except RuntimeError:
            return False


    def update(self) -> str:
        env = { "DEBIAN_FRONTEND": "noninteractive" }

        cmd = ["apt", "update"]
        return Command.run(cmd, env=env)

    def install(self, pkgs: list[str]) -> str:
        env = { "DEBIAN_FRONTEND": "noninteractive" }

        self.update()

        cmd = ["apt", "install", "-y", "--quiet"] + pkgs
        return Command.run(cmd, env=env)

class DNFPackageManager(PackageManager):
    @property
    def identifier(self):
        return "dnf"

    def installed(self, pkg_name: str) -> bool:
        try:
            cmd = ["dnf", "list", "installed", pkg_name]
            result = Command.run(cmd)
            return "No match" not in result
        except RuntimeError:
            return False

    def update(self) -> str:
        cmd = ["dnf", "update", "-y"]
        return Command.run(cmd)

    def install(self, pkgs: list[str]) -> str:
        cmd = ["dnf", "install", "-y"] + pkgs
        return Command.run(cmd)

class PackageManagerFactory:
    @classmethod
    def get_instance(cls) -> PackageManager:
        apt_marker = ["/etc/debian_version", "/etc/lsb-release"]
        for x in apt_marker:
            if Path(x).exists():
                logger.info("Looking for apt and dpkg-query")

                Command.find(command="apt")
                Command.find(command="dpkg-query")

                return AptPackageManager()

        dnf_marker = ["/etc/redhat-release", "/etc/os-release"]
        for x in dnf_marker:
            if Path(x).exists():
                logger.info("Identified RedHat, looking for dnf ...")

                Command.find(command="dnf")

                return DNFPackageManager()

        raise RuntimeError("Failed to identify package manager for current OS")
