"""Disposable #14 acceptance probe: deliberately fails without external I/O."""
def test_controlled_failure_for_autodev_handoff():
    raise AssertionError('Controlled AutoDev issue 14 probe; never merge this commit')
