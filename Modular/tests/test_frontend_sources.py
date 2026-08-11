"""Frontend source compilation and reference regression tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_all_jsx_sources_compile_with_babel():
    script = r"""
const fs = require("fs");
const Babel = require("./shadow_os_cache/js/babel.js");
const files = fs.readdirSync("frontend/scripts/components")
  .filter(name => name.endsWith(".js"))
  .map(name => "frontend/scripts/components/" + name)
  .concat(["frontend/scripts/app.js"]);
for (const file of files) {
  Babel.transform(fs.readFileSync(file, "utf8"), {presets: ["react"]});
}
"""
    subprocess.run(
        ["node", "-e", script],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_dashboard_declares_analytics_props():
    source = (PROJECT_ROOT / "frontend/scripts/components/dashboard.js").read_text()
    declaration = source[source.index("const DashboardView") : source.index("=>", source.index("const DashboardView"))]
    for prop in ("dailyMetrics", "setDailyMetrics", "correlations", "insights"):
        assert prop in declaration


def test_timeline_scale_is_component_scoped():
    source = (PROJECT_ROOT / "frontend/scripts/components/timer.js").read_text()
    config_index = source.index("const timelinePixelPerHour")
    scale_index = source.index("const pxPerMin")
    first_effect_index = source.index("useEffect")
    assert config_index < scale_index < first_effect_index
