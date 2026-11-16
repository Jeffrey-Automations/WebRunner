"""throttler: the package exports what its module-level acquire / throttle need to be usable."""
import je_web_runner.utils.throttler as throttler_package
from je_web_runner.utils.throttler import throttler as throttler_module


def test_package_exports_configure_global(tmp_path):
    assert "configure_global" in throttler_package.__all__
    assert throttler_package.configure_global is throttler_module.configure_global
    throttler_package.configure_global("leads-export-check", capacity=1, base_dir=str(tmp_path))
    with throttler_package.throttle("leads-export-check", timeout=1.0) as slot:
        assert slot.exists()
    assert not slot.exists()
