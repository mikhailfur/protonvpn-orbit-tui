"""Regression tests for issue #1: refresh after interactive sign-in.

These tests only use a temporary fake ``protonvpn`` executable.  They never
touch the real CLI, the real account, or its credentials.
"""

from __future__ import annotations

import atexit
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from contextlib import nullcontext, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = Path(tempfile.mkdtemp(prefix="orbit-signin-test-"))
STATE_FILE = TEST_ROOT / "state.json"
FAKE_CLI = TEST_ROOT / "protonvpn"

FAKE_CLI.write_text(
    textwrap.dedent(
        """\
        #!/usr/bin/env python3
        import json
        import os
        import sys
        from pathlib import Path

        state = json.loads(Path(os.environ["ORBIT_TEST_STATE"]).read_text())
        command = sys.argv[1] if len(sys.argv) > 1 else ""

        if command == "info":
            account = state.get("account") or ""
            if state.get("signed_in") and account:
                print(f"Account: '{account}'")
                raise SystemExit(0)
            print("You are not signed in.", file=sys.stderr)
            raise SystemExit(1)

        if command == "status":
            if state.get("connected"):
                print("Status: Connected")
                print(
                    f"Server: {state.get('server', 'JP#270')} "
                    f"in {state.get('location', 'Tokyo, Japan')}"
                )
                print(f"Load: {state.get('load', 43)}%")
                print(f"Protocol: {state.get('protocol', 'wireguard')}")
            else:
                print("Status: Disconnected")
            raise SystemExit(0)

        print(f"Unsupported fake CLI command: {command}", file=sys.stderr)
        raise SystemExit(2)
        """
    ),
    encoding="utf-8",
)
FAKE_CLI.chmod(0o755)
STATE_FILE.write_text(
    json.dumps({"signed_in": False, "connected": False}), encoding="utf-8"
)

os.environ["PROTONVPN_BIN"] = str(FAKE_CLI)
os.environ["XDG_CONFIG_HOME"] = str(TEST_ROOT / "config")
os.environ["XDG_CACHE_HOME"] = str(TEST_ROOT / "cache")
os.environ["ORBIT_TEST_STATE"] = str(STATE_FILE)

SPEC = importlib.util.spec_from_file_location(
    "proton_orbit_under_test", ROOT / "proton_orbit.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Could not load proton_orbit.py")
orbit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = orbit
SPEC.loader.exec_module(orbit)


def tearDownModule() -> None:
    shutil.rmtree(TEST_ROOT, ignore_errors=True)


atexit.register(shutil.rmtree, TEST_ROOT, ignore_errors=True)


def write_state(**updates: object) -> None:
    state = {"signed_in": False, "connected": False}
    state.update(updates)
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")


class FakeMainScreen:
    """Minimal MainScreen surface used by signin_interactive()."""

    def __init__(self, app: object) -> None:
        self.app = app
        self.statuses: list[tuple[str, str]] = []
        self.notifications: list[str] = []

    def set_status(self, message: str, kind: str = "info") -> None:
        self.statuses.append((message, kind))

    def notify(self, message: str, **_kwargs: object) -> None:
        self.notifications.append(message)

    def refresh_all(self) -> None:
        pass


class SigninOutcomeTests(unittest.TestCase):
    def test_successful_signin(self) -> None:
        self.assertEqual(
            orbit.signin_outcome(0, True, False, "", "test@example.com"),
            (True, "Signed in. Welcome back."),
        )

    def test_failed_signin_does_not_report_success(self) -> None:
        success, message = orbit.signin_outcome(1, False, False, "", "")
        self.assertFalse(success)
        self.assertIn("CLI exit code 1", message)

    def test_failed_signin_keeps_existing_session_message(self) -> None:
        success, message = orbit.signin_outcome(
            1, True, True, "existing@example.com", "existing@example.com"
        )
        self.assertFalse(success)
        self.assertIn("existing session unchanged", message)

    def test_exit_zero_without_account_is_not_success(self) -> None:
        success, message = orbit.signin_outcome(0, False, False, "", "")
        self.assertFalse(success)
        self.assertIn("did not complete", message)

    def test_failure_includes_cli_error_detail(self) -> None:
        success, message = orbit.signin_outcome(
            1,
            False,
            False,
            "",
            "",
            "Error: Authentication failed. Please check your username and password.",
        )
        self.assertFalse(success)
        self.assertIn("Authentication failed", message)


class ForcedRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.app = orbit.OrbitApp()
        self.app.busy = True

    async def test_account_refresh_bypasses_busy_only_when_forced(self) -> None:
        self.app.signed_in = False
        self.app.account_name = ""
        write_state(signed_in=True, account="orbit-test@example.com")

        # Background refreshes must still respect the operation guard.
        self.assertFalse(await self.app.refresh_account())
        self.assertFalse(self.app.signed_in)

        # The post-sign-in refresh must be able to read the new identity.
        self.assertTrue(await self.app.refresh_account(force=True))
        self.assertTrue(self.app.signed_in)
        self.assertEqual(self.app.account_name, "orbit-test@example.com")

    async def test_status_refresh_bypasses_busy_only_when_forced(self) -> None:
        write_state(
            connected=True,
            server="JP#270",
            location="Tokyo, Japan",
            load=43,
            protocol="wireguard",
        )
        self.assertFalse(self.app.connection.connected)

        self.assertFalse(await self.app.refresh_status())
        self.assertFalse(self.app.connection.connected)

        self.assertTrue(await self.app.refresh_status(force=True))
        self.assertTrue(self.app.connection.connected)
        self.assertEqual(self.app.connection.server_name, "JP#270")


class SigninInteractiveTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.app = orbit.OrbitApp()
        self.screen = FakeMainScreen(self.app)
        self.app.suspend = lambda: nullcontext()  # type: ignore[method-assign]

        async def load_countries() -> bool:
            return True

        self.app.load_countries_from_cli = load_countries  # type: ignore[method-assign]

    async def test_successful_signin_refreshes_while_busy(self) -> None:
        write_state(signed_in=False, connected=False)
        self.app.signed_in = False
        self.app.account_name = ""

        def fake_run(
            cmd: list[str], check: bool = False, **_kwargs: object
        ) -> orbit.subprocess.CompletedProcess:
            write_state(signed_in=True, account="new@example.com", connected=False)
            return orbit.subprocess.CompletedProcess(cmd, 0)

        with patch.object(orbit.subprocess, "run", side_effect=fake_run):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                await orbit.MainScreen.signin_interactive(
                    self.screen, "new@example.com", False
                )

        self.assertFalse(self.app.busy)
        self.assertTrue(self.app.signed_in)
        self.assertEqual(self.app.account_name, "new@example.com")
        self.assertEqual(self.screen.statuses[-1], ("Signed in. Welcome back.", "ok"))
        self.assertIn("Signed in successfully.", self.screen.notifications)

    async def test_failed_signin_with_existing_session_is_not_success(self) -> None:
        write_state(signed_in=True, account="existing@example.com", connected=False)
        self.app.signed_in = True
        self.app.account_name = "existing@example.com"

        def fake_run(
            cmd: list[str], check: bool = False, **_kwargs: object
        ) -> orbit.subprocess.CompletedProcess:
            write_state(signed_in=True, account="existing@example.com", connected=False)
            return orbit.subprocess.CompletedProcess(
                cmd, 1, stderr="Error: Authentication failed."
            )

        with patch.object(orbit.subprocess, "run", side_effect=fake_run):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                await orbit.MainScreen.signin_interactive(
                    self.screen, "existing@example.com", False
                )

        self.assertFalse(self.app.busy)
        self.assertTrue(self.app.signed_in)
        status, kind = self.screen.statuses[-1]
        self.assertEqual(kind, "error")
        self.assertIn("existing session unchanged", status)
        self.assertNotIn("Signed in successfully.", self.screen.notifications)


if __name__ == "__main__":
    unittest.main()
