"""The CPU and memory script's pure parts: medians, growth, comparing, limits, the data folder
and its README; the measuring loop with stand-ins for the runs, and the stop of a run. The
measuring itself is proven by a recorded run (docs/development.md)."""

import contextlib
import importlib.util
import json
import os
import signal
import subprocess
import time
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
        "warmup_runs": 1,
        "runs_each": 5,
        "rounds": [measure_use.in_order([v["label"] for v in versions], r) for r in range(6)],
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


def test_a_sample_that_changed_between_runs_is_not_compared():
    varied = {**SAMPLE, "varies": True}
    a, b = version("0.9.2"), version("main@1", 99.0, sample=varied)
    assert measure_use.compare(a, b) == (
        [],
        ["Not compared: the sample changed between runs of main@1."],
    )
    a = version("0.9.2", sample=varied)
    assert measure_use.compare(a, b)[1] == [
        "Not compared: the sample changed between runs of 0.9.2 and main@1."
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
    assert len(summary.read_text().splitlines()) == 3


def test_a_gateway_limit_counts_only_when_the_night_has_the_gateway(monkeypatch):
    b = version("main@1")
    night = result("night", [version("0.9.2"), b])
    monkeypatch.setitem(measure_use.GATEWAY_LIMITS, "idle_cpu_s", 0.3)
    assert measure_use.broken_limits(night) == []
    b["gateway"] = {"summary": {"idle_cpu_s": {"median": 0.5, "low": 0.4, "high": 0.6}}}
    assert measure_use.broken_limits(night) == [
        "main@1 gateway idle CPU in 30 s (s): 0.5 (0.4–0.6), median over 0.3."
    ]


def test_the_gateway_has_its_own_series_and_the_readme_shows_only_its_newest(tmp_path):
    # Adding the gateway left the page series alone.
    assert measure_use.SERIES == {"page": 1, "gateway": 1}
    cell = {"median": 0.2, "low": 0.1, "high": 0.3}
    gate = {"summary": {"idle_cpu_s": cell, "growth_mb": cell}}
    for day, label, gateway_series in (("20", "main@1", 1), ("21", "main@2", 2)):
        night = result("night", [version("0.9.2"), {**version(label), "gateway": gate}])
        night["date"], night["series"]["gateway"] = f"2026-11-{day}", gateway_series
        measure_use.store(night, tmp_path)
    text = (tmp_path / "README.md").read_text()
    rows = {line.split(" | ")[2]: line for line in text.splitlines() if line.startswith("| 2026-")}
    assert rows["main@2"].count("0.2 (0.1–0.3)") == 2
    assert "0.2 (0.1–0.3)" not in rows["main@1"]  # an older gateway series: not shown


def test_the_cutoff_is_an_hour_after_the_first_upload():
    files = [
        {"upload_time_iso_8601": "2026-11-14T17:20:44.100000Z"},
        {"upload_time_iso_8601": "2026-11-14T17:20:42.960586Z"},
    ]
    assert measure_use.cutoff(files) == "2026-11-14T18:20:42Z"


def test_the_script_imports_nothing_of_kitden_and_needs_psutil_only_to_measure():
    text = (ROOT / "scripts/measure-use.py").read_text()
    assert "import kitden" not in text and "from kitden" not in text
    # psutil is imported inside the measuring functions, never at the top.
    assert "\nimport psutil" not in text and "\nfrom psutil" not in text
    assert measure_use.SERIES["page"] == 1


def test_a_night_writes_its_file_and_a_missing_release_file_only(tmp_path):
    first = result("night", [version("0.9.2"), version("main@1")], date="2026-11-20")
    measure_use.store(first, tmp_path)
    kept = json.loads((tmp_path / "releases/0.9.2.json").read_text())
    assert kept["kind"] == "night" and kept["version"]["label"] == "0.9.2"
    assert "gateway_rounds" not in kept
    second = result("night", [version("0.9.2", peak=70.0), version("main@2")], date="2026-11-21")
    measure_use.store(second, tmp_path)
    assert sorted(p.name for p in (tmp_path / "nights").iterdir()) == [
        "2026-11-20.json",
        "2026-11-21.json",
    ]
    assert json.loads((tmp_path / "releases/0.9.2.json").read_text()) == kept
    assert (tmp_path / "README.md").exists()


def test_a_backfill_overwrites_the_release_files(tmp_path):
    measure_use.store(result("night", [version("0.9.2"), version("main@1")]), tmp_path)
    backfill = result("backfill", [version("0.3.0"), version("0.9.2", peak=61.0)], run_id="77")
    measure_use.store(backfill, tmp_path)
    kept = json.loads((tmp_path / "releases/0.9.2.json").read_text())
    assert kept["kind"] == "backfill" and kept["run_id"] == "77"
    # The swapped order and the warm-up are kept with the numbers.
    assert kept["warmup_runs"] == 1
    assert kept["rounds"][:2] == [["0.3.0", "0.9.2"], ["0.9.2", "0.3.0"]]
    assert kept["version"]["page"]["summary"]["peak_mb"]["median"] == 61.0


def test_store_refuses_a_date_or_label_that_is_no_plain_file_name(tmp_path):
    # The values become file names in a job that holds a write token.
    with pytest.raises(SystemExit, match="date"):
        measure_use.store(
            result("night", [version("0.9.2"), version("main@1")], date="../x"), tmp_path
        )
    with pytest.raises(SystemExit, match="label"):
        measure_use.store(result("night", [version("../x"), version("main@1")]), tmp_path)
    with pytest.raises(SystemExit, match="label"):
        measure_use.store(result("backfill", [version("0.3.0"), version("../x")]), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_two_versions_with_one_label_are_refused_before_anything_runs(tmp_path, monkeypatch):
    def no_process(*args, **kwargs):
        raise AssertionError("nothing may run")

    monkeypatch.setattr(measure_use.subprocess, "run", no_process)
    monkeypatch.setattr(measure_use.subprocess, "Popen", no_process)
    out = tmp_path / "night.json"
    with pytest.raises(SystemExit, match="own label"):
        measure_use.main(["run", "--out", str(out), "0.9.2=/a/kitden", "0.9.2=/b/kitden"])
    assert not out.exists()


def test_a_backfill_with_the_gateway_is_refused_before_anything_runs(tmp_path, monkeypatch):
    # The gateway is measured on nights only, never for old releases.
    def no_process(*args, **kwargs):
        raise AssertionError("nothing may run")

    monkeypatch.setattr(measure_use.subprocess, "run", no_process)
    monkeypatch.setattr(measure_use.subprocess, "Popen", no_process)
    out = tmp_path / "backfill.json"
    with pytest.raises(SystemExit, match="nights only"):
        measure_use.main(
            ["run", "--out", str(out), "--backfill", "--gateway", "/e/python", "0.3.0=/a/kitden"]
        )
    assert not out.exists()


def test_store_refuses_a_kind_that_is_no_night_or_backfill(tmp_path):
    with pytest.raises(SystemExit, match="kind"):
        measure_use.store(result("nightly", [version("0.9.2"), version("main@1")]), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_the_readme_has_both_tables_and_no_chart(tmp_path):
    old = result(
        "backfill", [version("0.3.0", peak=50.0), version("0.4.0")], run_id="1", date="2026-11-18"
    )
    new = result(
        "backfill",
        [version("0.10.0", peak=60.0), version("0.9.2", peak=59.0)],
        run_id="2",
        date="2026-11-19",
        cpu="Intel Xeon 8370C",
    )
    for one in (old, new, result("night", [version("0.9.2"), version("main@1")])):
        measure_use.store(one, tmp_path)
    text = (tmp_path / "README.md").read_text()
    # Releases in version order, each with its median, spread, CPU and how it was measured.
    rows = [line for line in text.splitlines() if line.startswith("| 0.")]
    assert [row.split(" | ")[0] for row in rows] == ["| 0.3.0", "| 0.4.0", "| 0.9.2", "| 0.10.0"]
    assert "| 50.0 (49.0–51.0) |" in rows[0] and "AMD EPYC 7763 | backfill 2026-11-18 |" in rows[0]
    assert "| 2026-11-20 | 0.9.2 | main@1 |" in text
    # The charts are on the desk page, drawn from chart.json; the README has none.
    assert "mermaid" not in text and "kitden-sdlc/desk/#use" in text


def test_the_chart_comes_from_one_backfill_run_with_main_and_no_night_changes_it(tmp_path):
    backfill = result(
        "backfill",
        [
            version("0.10.0", peak=60.0),
            version("0.9.2", peak=59.0),
            version("main@abc1234", commit="abc1234"),
        ],
        run_id="2",
        date="2026-11-19",
        cpu="Intel Xeon 8370C",
    )
    measure_use.store(backfill, tmp_path)
    chart = json.loads((tmp_path / "chart.json").read_text())
    assert {k: chart[k] for k in ("series", "run_id", "date", "cpu", "runs")} == {
        "series": 1,
        "run_id": "2",
        "date": "2026-11-19",
        "cpu": "Intel Xeon 8370C",
        "runs": 5,
    }
    # The releases in version order, then this commit, all from the one run (B0 rule 8).
    assert [(p["label"], p["commit"]) for p in chart["points"]] == [
        ("0.9.2", None),
        ("0.10.0", None),
        ("main", "abc1234"),
    ]
    assert chart["points"][0]["peak_mb"] == {"median": 59.0, "low": 58.0, "high": 60.0}
    assert sorted(p.name for p in (tmp_path / "releases").iterdir()) == [
        "0.10.0.json",
        "0.9.2.json",
    ]
    # A night, on whatever runner it got, never changes the chart.
    measure_use.store(result("night", [version("0.9.2"), version("main@def5678")]), tmp_path)
    assert json.loads((tmp_path / "chart.json").read_text()) == chart


def test_the_readme_shows_the_newest_series_only(tmp_path):
    measure_use.store(result("night", [version("0.9.2"), version("main@1")], series=1), tmp_path)
    measure_use.store(
        result("night", [version("0.9.2"), version("main@2")], series=2, date="2026-11-21"),
        tmp_path,
    )
    text = (tmp_path / "README.md").read_text()
    assert "Page series 2" in text and "main@2" in text and "main@1" not in text


def test_the_nights_table_shows_the_last_14_newest_first_with_notes(tmp_path):
    for day in range(1, 17):
        night = result("night", [version("0.9.2"), version("main@1")], date=f"2026-12-{day:02}")
        night["notes"] = ["Not compared: the samples differ."] if day == 16 else []
        measure_use.store(night, tmp_path)
    text = (tmp_path / "README.md").read_text()
    days = [line[2:12] for line in text.splitlines() if line.startswith("| 2026-12-")]
    assert days[0] == "2026-12-16" and days[-1] == "2026-12-03" and len(days) == 14
    assert "| Not compared: the samples differ. |" in text


def test_the_development_page_says_how_it_measures():
    text = " ".join((ROOT / "docs/development.md").read_text().split())
    assert "## CPU and memory" in text and "uses no Kitden code" in text
    assert "The measurement changes alone" in text and "`use-numbers`" in text


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_a_stopped_run_leaves_nothing_of_its_process_group():
    # A grandchild in the child's group that ignores SIGTERM must not outlive the run.
    child = subprocess.Popen(
        ["/bin/sh", "-c", "(trap '' TERM; echo trapped; exec sleep 60) & echo $!; wait"],
        stdout=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    assert child.stdout is not None
    # Its pid and "trapped" (SIGTERM is ignored from now on), in either order.
    lines = {child.stdout.readline().strip(), child.stdout.readline().strip()}
    assert "trapped" in lines
    grandchild = int((lines - {"trapped"}).pop())
    child.stdout.close()
    try:
        measure_use._stop(child)
        deadline = time.monotonic() + 5
        while _alive(grandchild) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not _alive(grandchild)
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.kill(grandchild, signal.SIGKILL)


def _stand_ins(monkeypatch):
    """Stand-ins for the runs and the venvs: each run returns its call number in every metric."""
    calls = []

    def one_run(scenario):
        def run(kitden, root, *rest):
            calls.append((scenario, str(kitden), *rest))
            n = float(len(calls))
            return {
                **dict.fromkeys(measure_use.PAGE_METRICS + measure_use.GATEWAY_METRICS, n),
                "sample": {"items": 1, "bytes": 2},
                "exit": 0,
            }

        return run

    monkeypatch.setattr(
        measure_use, "packages", lambda kitden: {"python": "3.13", "packages": ["kitden==1"]}
    )
    monkeypatch.setattr(measure_use, "environment", lambda: {"cpu": "stand-in"})
    monkeypatch.setattr(measure_use, "page_run", one_run("page"))
    monkeypatch.setattr(measure_use, "gateway_run", one_run("gateway"))
    return calls


def _measured(tmp_path, *args):
    out = tmp_path / "result.json"
    assert measure_use.main(["run", "--out", str(out), "--runs", "2", *args]) == 0
    return json.loads(out.read_text())


def test_a_night_measures_in_turn_and_throws_the_warm_up_away(monkeypatch, tmp_path):
    calls = _stand_ins(monkeypatch)
    got = _measured(tmp_path, "0.9.2=/e/a/bin/kitden", "main@1=/e/b/bin/kitden")
    rounds = [["0.9.2", "main@1"], ["main@1", "0.9.2"], ["0.9.2", "main@1"]]
    assert got["rounds"] == rounds
    path = {"0.9.2": "/e/a/bin/kitden", "main@1": "/e/b/bin/kitden"}
    assert calls == [("page", path[label]) for labels in rounds for label in labels]
    # Calls 1 and 2 are the warm-up; then B is 3, A is 4, A is 5, B is 6.
    a, b = got["versions"]
    assert [run["ready_s"] for run in a["page"]["runs"]] == [4.0, 5.0]
    assert [run["ready_s"] for run in b["page"]["runs"]] == [3.0, 6.0]
    # Without --gateway: the page only, and a result shaped as before.
    assert got["series"] == {"page": 1} and "gateway_rounds" not in got
    assert "gateway" not in a and "gateway" not in b


def test_the_gateways_rounds_come_after_all_the_pages(monkeypatch, tmp_path):
    calls = _stand_ins(monkeypatch)
    got = _measured(
        tmp_path, "--gateway", "/e/python", "0.9.2=/e/a/bin/kitden", "main@1=/e/b/bin/kitden"
    )
    rounds = [["0.9.2", "main@1"], ["main@1", "0.9.2"], ["0.9.2", "main@1"]]
    assert got["rounds"] == got["gateway_rounds"] == rounds
    assert got["series"] == {"page": 1, "gateway": 1}
    path = {"0.9.2": "/e/a/bin/kitden", "main@1": "/e/b/bin/kitden"}
    page = [("page", path[label]) for labels in rounds for label in labels]
    echo = Path("/e/python")
    gateway = [("gateway", path[label], echo) for labels in rounds for label in labels]
    assert calls == page + gateway
    # Calls 7 and 8 are the gateway's warm-up; then B is 9, A is 10, A is 11, B is 12.
    a, b = got["versions"]
    assert [run["ready_s"] for run in a["page"]["runs"]] == [4.0, 5.0]
    assert [run["ready_s"] for run in a["gateway"]["runs"]] == [10.0, 11.0]
    assert [run["ready_s"] for run in b["gateway"]["runs"]] == [9.0, 12.0]
    assert b["gateway"]["summary"]["calls_cpu_s"] == {"median": 10.5, "low": 9.0, "high": 12.0}


def test_a_backfill_measures_every_version_the_same_number_of_times(monkeypatch, tmp_path):
    calls = _stand_ins(monkeypatch)
    got = _measured(
        tmp_path, "--backfill", "0.3.0=/e/a/kitden", "0.4.0=/e/b/kitden", "main@c=/e/c/kitden"
    )
    rounds = [["0.3.0", "0.4.0", "main@c"], ["0.4.0", "main@c", "0.3.0"]]
    rounds.append(["main@c", "0.3.0", "0.4.0"])
    assert got["rounds"] == rounds
    path = {"0.3.0": "/e/a/kitden", "0.4.0": "/e/b/kitden", "main@c": "/e/c/kitden"}
    assert calls == [("page", path[label]) for labels in rounds for label in labels]
    runs = {v["label"]: [run["ready_s"] for run in v["page"]["runs"]] for v in got["versions"]}
    assert runs == {"0.3.0": [6.0, 8.0], "0.4.0": [4.0, 9.0], "main@c": [5.0, 7.0]}
