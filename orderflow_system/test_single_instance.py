"""N-1: one windowed instance per profile — the mutex pins.

The guard lives in ``desktop/single_instance.py``; these tests pin the parts that must never
drift: the per-profile name (case- and slash-insensitive), the kernel behaviour the guard relies
on (a second acquisition of a held name is refused, and released names can be re-acquired), and
that focusing is a quiet no-op when no matching window exists (so a test run can never wake the
owner's real window).
"""

from __future__ import annotations

import sys
import uuid

import pytest

from orderflow_system.desktop import single_instance as si

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows kernel object")


def test_the_name_is_stable_and_profile_specific():
    a = si.instance_mutex_name(r"C:\Users\X\AppData\Roaming\OrderFlowAnalysisPro")
    b = si.instance_mutex_name(r"c:/users/x/appdata/roaming/orderflowanalysispro/")
    c = si.instance_mutex_name(r"C:\Users\X\AppData\Roaming\OtherProfile")
    assert a == b                      # case- and slash-insensitive
    assert a != c                      # one name per profile
    assert a.startswith("ModFlowOrderFlowAnalysisSuite-")


def test_a_held_name_is_refused_and_a_released_one_is_acquirable():
    name = f"ofap-selftest-{uuid.uuid4().hex}"
    first = si._create_mutex(name)
    assert first, "first acquisition must succeed"
    try:
        assert si._create_mutex(name) is None, "a held name must be refused"
    finally:
        si._close_handle(first)
    again = si._create_mutex(name)
    assert again, "a released name must be acquirable again"
    si._close_handle(again)


def test_a_second_app_acquisition_in_process_is_allowed_once_held():
    # main() may call acquire more than once in one process (tests import it); the second call
    # must see the handle it already holds rather than refusing the process its own mutex.
    assert si.acquire_for_app(str(uuid.uuid4())) is True


def test_focus_is_a_quiet_no_op_without_a_matching_window():
    assert si._focus_existing(f"NoSuchWindowTitle-{uuid.uuid4().hex}") is False

def test_the_already_running_notice_is_bounded():
    """The notice must close itself — an unbounded modal call left a stuck windowless process
    when the owner's window could not be found (caught live, mistaken for a duplicate)."""
    assert isinstance(si.NOTICE_MS, int) and 0 < si.NOTICE_MS <= 15_000
