from naic_bench.package_manager import PackageManagerFactory
from naic_bench.utils.command import Command

def test_PackageManagerFactory(monkeypatch):

    pkg_mgr = PackageManagerFactory.get_instance()

    assert pkg_mgr.installed("git")
    assert not pkg_mgr.installed("unknown-package")

    installation_commands = []
    def mock_command_run(cmd, env: dict = {}, requires_root: bool = True):
        installation_commands.append([cmd, env, requires_root])

    monkeypatch.setattr(Command, "run", mock_command_run)

    pkg_mgr.install(["git", "g++"])

    assert installation_commands == [[['apt', 'update'], {'DEBIAN_FRONTEND': 'noninteractive'}, True], [['apt', 'install', '-y', '--quiet', 'git', 'g++'], {'DEBIAN_FRONTEND': 'noninteractive'}, True]]
