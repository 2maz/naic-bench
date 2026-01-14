
from naic_bench.package_manager import PackageManagerFactory

def test_PackageManagerFactory():
    pkg_mgr = PackageManagerFactory.get_instance()

    assert pkg_mgr.installed("git")
    assert not pkg_mgr.installed("unknown-package")

    assert pkg_mgr.install(["git", "g++"])
