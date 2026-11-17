"""The CPU and memory script's pure parts: medians, growth, comparing, limits, the data folder
and its README. The measuring itself is proven by a recorded run (docs/development.md)."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("measure_use", ROOT / "scripts/measure-use.py")
measure_use = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(measure_use)

SAMPLE = {"items": 548, "bytes": 407577, "varies": False}


def version(label, peak=58.0, cpu=0.7, idle=0.06, grow=0.0, sample=SAMPLE, commit=None):
    s = {
        "peak_mb": {"median": peak, "low": peak - 1, "high": peak + 1},
        "cpu_ready_s": {"median": cpu, "low": cpu, "high": cpu},
        "idle_cpu_s": {"median": idle, "low": idle, "high": idle},
        "growth_mb": {"median": grow, "low": grow, "high": grow},
        "ready_s": {"median": 3.0, "low": 1.0, "high": 9.0},
    }
    return {"label": label, "commit": commit, "page": {"sample": sample, "summary": s, "runs": []}}


def result(kind, versions, date="2026-11-20", run_id="1", series=1, cpu="AMD EPYC 7763"):
    return {
        "series": {"page": series},
        "kind": kind,
        "run_id": run_id,
        "date": date,
        "time": f"{date}T03:40:00Z",
        "warm": True,
        "runs_each": 5,
        "env": {"cpu": cpu, "runner_image": "ubuntu24"},
        "versions": versions,
        "warnings": [],
        "notes": [],
    }


def test_a_spread_is_the_median_with_the_lowest_and_highest_run():
    assert measure_use.spread([0.7, 0.66, 0.82, 0.62, 0.75]) == {
        "median": 0.7,
        "low": 0.62,
        "high": 0.82,
    }


def test_each_round_starts_one_version_later():
    assert [measure_use.in_order(["A", "B"], r) for r in range(3)] == [
        ["A", "B"],
        ["B", "A"],
        ["A", "B"],
    ]
    assert measure_use.in_order(["0.3.0", "0.4.0", "0.5.0"], 4) == ["0.4.0", "0.5.0", "0.3.0"]


def test_growth_starts_after_the_first_200_calls():
    readings = [58.5, 57.6, 57.7, 57.7, 57.6, 57.7, 57.7, 57.7, 57.7, 58.1]
    assert measure_use.growth(readings) == 0.5


def test_peak_memory_is_kib_on_linux_and_bytes_on_macos():
    assert measure_use.peak_mb(57_000, "Linux") == 58.368
    assert measure_use.peak_mb(58_368_000, "Darwin") == 58.368


def test_a_label_names_a_release_or_a_commit():
    assert measure_use.label_of("0.9.2=/e/a/bin/kitden") == ("0.9.2", None, Path("/e/a/bin/kitden"))
    assert measure_use.label_of("main@f028492=/e/b/bin/kitden")[:2] == ("main@f028492", "f028492")
    with pytest.raises(ValueError):
        measure_use.label_of("/e/b/bin/kitden")


def test_b_warns_only_above_its_share_of_a():
    a = version("0.9.2", peak=58.0, cpu=0.70)
    assert measure_use.compare(a, version("main@1", peak=66.6, cpu=0.87)) == ([], [])
    warnings, notes = measure_use.compare(a, version("main@1", peak=66.8, cpu=0.88))
    assert notes == [] and len(warnings) == 2
    assert warnings[0].startswith(
        "main@1 peak memory (MB): 66.8 (65.8–67.8) against 58.0 (57.0–59.0) for 0.9.2, "
        "15% more by median"
    )


def test_different_samples_are_not_compared_and_say_why():
    other = {"items": 560, "bytes": 410000, "varies": False}
    warnings, notes = measure_use.compare(version("0.9.2"), version("main@1", 99.0, sample=other))
    assert warnings == []
    assert notes == [
        "Not compared: the samples differ (0.9.2: 548 items, 407577 bytes; "
        "main@1: 560 items, 410000 bytes)."
    ]


def test_limits_are_off_while_they_are_none(monkeypatch):
    night = result("night", [version("0.9.2"), version("main@1", peak=500.0, grow=50.0)])
    assert measure_use.broken_limits(night) == []
    monkeypatch.setitem(measure_use.PAGE_LIMITS, "peak_mb", 150.0)
    monkeypatch.setitem(measure_use.PAGE_LIMITS, "growth_mb", 10.0)
    assert measure_use.broken_limits(night) == [
        "main@1 page peak memory (MB): 500.0 (499.0–501.0), median over 150.0.",
        "main@1 page memory growth over the calls (MB): 50.0 (50.0–50.0), median over 10.0.",
    ]
    # A backfill compares nothing and fails nothing.
    assert measure_use.broken_limits(result("backfill", night["versions"])) == []


def test_a_broken_limit_fails_the_check_and_a_warning_does_not(monkeypatch, tmp_path, capsys):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    night = result("night", [version("0.9.2"), version("main@1", peak=80.0)])
    night["warnings"] = ["main@1 peak memory (MB): 80.0 against 58.0 for 0.9.2, 38% more."]
    assert measure_use.check(night) == 0
    assert capsys.readouterr().out.startswith("::warning::main@1 peak memory")
    monkeypatch.setitem(measure_use.PAGE_LIMITS, "peak_mb", 70.0)
    assert measure_use.check(night) == 1
    error = "::error::main@1 page peak memory (MB): 80.0 (79.0–81.0), median over 70.0."
    assert error in capsys.readouterr().out
    assert summary.read_text().count("- ") == 3


def test_the_cutoff_is_an_hour_after_the_first_upload():
    files = [
        {"upload_time_iso_8601": "2026-11-14T17:20:44.100000Z"},
        {"upload_time_iso_8601": "2026-11-14T17:20:42.960586Z"},
    ]
    assert measure_use.cutoff(files) == "2026-11-14T18:20:42Z"


def test_the_script_imports_nothing_of_kitden_and_needs_psutil_only_to_measure():
    text = (ROOT / "scripts/measure-use.py").read_text()
    assert "import kitden" not in text and "from kitden" not in text
    assert "\nimport psutil" not in text  # psutil is imported inside the measuring functions
    assert measure_use.SERIES["page"] == 1
