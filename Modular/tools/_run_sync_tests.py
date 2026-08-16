"""Run each sandboxed sync test class with an individual timeout."""
import contextlib
import io
import sys
import threading
import unittest

sys.path.insert(0, "tests")

import test_sync_sandboxed as mod
import test_sync_multi_machine as multi

classes = [
    mod.TestExportLogic,
    mod.TestBasicMerge,
    mod.TestBidirectionalMerge,
    mod.TestConflictResolution,
    mod.TestDeletionPropagation,
    mod.TestSettingsSync,
    mod.TestForceSyncMasterOverwrite,
    mod.TestHardClone,
    mod.TestFullGitSyncCycle,
    mod.TestEdgeCases,
    mod.TestMultiDeviceTimeline,
    mod.TestSyncManagerHelperMethods,
    mod.TestGitRepoSetup,
    mod.TestComprehensiveDataTypes,
    multi.TestMultiMachineSync,
]


class TimeoutError_(Exception):
    pass


def run_with_timeout(fn, seconds):
    result = {}

    def runner():
        try:
            fn()
            result["ok"] = True
        except BaseException as e:  # noqa: BLE001
            result["err"] = e

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        return TimeoutError_(f"timed out after {seconds}s")
    if "err" in result:
        return result["err"]
    return None


for cls in classes:
    buf = io.StringIO()

    def run_suite(buf=buf, cls=cls):
        suite = unittest.TestLoader().loadTestsFromTestCase(cls)
        runner = unittest.TextTestRunner(verbosity=1, stream=buf)
        result = runner.run(suite)
        buf.write(f"\nRESULT: success={result.wasSuccessful()} failures={len(result.failures)} errors={len(result.errors)}\n")

    err = run_with_timeout(run_suite, 240)
    if err is None:
        status = "OK"
    elif isinstance(err, TimeoutError_):
        status = "TIMEOUT"
    else:
        status = f"ERROR {type(err).__name__}: {err}"
    sys.stdout.write(f"### {cls.__name__}: {status}\n")
    sys.stdout.flush()
    # print partial output for non-ok results
    if status != "OK":
        sys.stdout.write(buf.getvalue()[-1500:] + "\n")
        sys.stdout.flush()