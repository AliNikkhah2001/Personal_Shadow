"""Launch the Qt WebEngine UI and exercise dashboard and timer navigation."""

from __future__ import annotations

import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from core_sys import config
from main import MindPalaceWebOS


class RuntimeSmokeTest:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.window = MindPalaceWebOS()
        self.window.show()
        self.dashboard_ok = False
        self.timer_values: list[str] = []

    def run(self) -> int:
        QTimer.singleShot(6_000, self._open_dashboard)
        QTimer.singleShot(8_000, self._check_dashboard)
        QTimer.singleShot(9_000, self._open_hub)
        QTimer.singleShot(10_000, self._read_timer)
        QTimer.singleShot(10_500, self._start_timer)
        QTimer.singleShot(13_500, self._read_timer)
        QTimer.singleShot(14_000, self._finish)
        QTimer.singleShot(20_000, self._timeout)
        return self.app.exec()

    @property
    def page(self):
        return self.window.browser.page()

    def _open_dashboard(self) -> None:
        self._click_button("Dashboard")

    def _check_dashboard(self) -> None:
        self.page.runJavaScript(
            "document.body.innerText.toLowerCase().includes('dashboard')",
            self._record_dashboard,
        )

    def _record_dashboard(self, result) -> None:
        self.dashboard_ok = bool(result)
        print(f"DASHBOARD_OK={self.dashboard_ok}", flush=True)

    def _open_hub(self) -> None:
        self._click_button("Productivity Hub")

    def _start_timer(self) -> None:
        self._click_button("Start", exact=True)

    def _read_timer(self) -> None:
        self.page.runJavaScript(
            "document.body.innerText.match(/\\b\\d{2}:\\d{2}\\b/)?.[0] || ''",
            self._record_timer,
        )

    def _record_timer(self, result) -> None:
        self.timer_values.append(str(result))
        print(f"TIMER_VALUE={result}", flush=True)

    def _click_button(self, label: str, *, exact: bool = False) -> None:
        comparison = "=== label.toLowerCase()" if exact else ".includes(label.toLowerCase())"
        script = f"""
            (() => {{
                const label = {label!r};
                const button = [...document.querySelectorAll('button')]
                    .find(item => item.innerText.trim().toLowerCase(){comparison});
                if (button) button.click();
                return Boolean(button);
            }})()
        """
        self.page.runJavaScript(
            script, lambda result: print(f"CLICK_{label.upper().replace(' ', '_')}={result}", flush=True)
        )

    def _finish(self) -> None:
        timer_ok = len(self.timer_values) == 2 and self.timer_values[0] != self.timer_values[1]
        print(f"TIMER_OK={timer_ok}", flush=True)
        self.window.bridge._handle_stop_timer({})
        self.app.exit(0 if self.dashboard_ok and timer_ok else 1)

    def _timeout(self) -> None:
        print("SMOKE_TIMEOUT=True", flush=True)
        self.app.exit(2)


def main() -> int:
    config.cfg["quiet_mode"] = True
    app = QApplication(sys.argv)
    return RuntimeSmokeTest(app).run()


if __name__ == "__main__":
    raise SystemExit(main())
