"""Measure the CPU and memory a `kitden` command uses, from outside, so any release since 0.3.0
can be measured the same way (docs/development.md, CPU and memory).

    run --out FILE [--runs 5] [--backfill] [--run-id ID] LABEL=KITDEN ...
    check FILE          print the warnings; exit 1 when a limit is broken
    store FILE DATA     put FILE into the data folder (nights/, releases/), rebuild DATA/README.md
    report DATA         rebuild DATA/README.md only
    cutoff VERSION PYPI_JSON   the --exclude-newer time for a release: its upload + 1 hour

LABEL is a release version (`0.9.2`) or `main@<commit>`; KITDEN is the `kitden` of a plain venv.
A night gives two: the newest release (A), then this commit (B). `--backfill` takes any number of
releases and compares nothing. Every version gets one warm-up run, thrown away, then `--runs`
runs, in turn, each round starting one version later (A B, B A, A B ...).

Standard library only, plus psutil for `run` (`uv run --with psutil==7.2.2`). It imports nothing
of Kitden: it must run against old releases. Never run it on the real home folder: every run
gets a sandbox HOME and temp folder of its own.
"""

import os
import re
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

# One series number per scenario. Raise a scenario's number with any change to what or how it
# is measured. Numbers of two series are never compared or drawn together; a new page series
# needs a new backfill.
SERIES = {"page": 1}
IDLE_SECONDS = 30
CALLS = 1000
EVERY = 100  # read the memory every this many calls
GROWTH_FROM = 200  # growth = the last reading minus the reading after this many calls
WARMUP = 1
GIVE_UP_SECONDS = 120
STOP_SECONDS = 10
MB = 1_000_000
# A night warns when B's median is worse than A's by more than this share.
WARN = {"peak_mb": 0.15, "cpu_ready_s": 0.25}
# A night fails when B's median is over a limit. None: off (the first 7 nights only record).
PAGE_LIMITS: dict[str, float | None] = {
    "peak_mb": None,
    "cpu_ready_s": None,
    "idle_cpu_s": None,
    "growth_mb": None,
}
PAGE_METRICS = ("peak_mb", "cpu_ready_s", "idle_cpu_s", "growth_mb", "ready_s")
NAMES = {
    "peak_mb": "peak memory (MB)",
    "cpu_ready_s": "CPU to ready (s)",
    "idle_cpu_s": "idle CPU in 30 s (s)",
    "growth_mb": "memory growth over the calls (MB)",
    "ready_s": "time to ready (s), not compared",
}
CHARTED = ("peak_mb", "cpu_ready_s")  # chart.json: the desk page's two charts, by release
NIGHTS_SHOWN = 14
LINK = re.compile(r"Open: (http://127\.0\.0\.1:(\d+)/\?token=(\S+))")


# --- Pure parts (unit tested) ---


def spread(values: list[float]) -> dict:
    """A median with the lowest and highest run, rounded for reading."""
    return {
        "median": round(statistics.median(values), 3),
        "low": round(min(values), 3),
        "high": round(max(values), 3),
    }


def _cell(value: dict) -> str:
    """How every number is shown: the median, then the lowest and highest run."""
    return f"{value['median']} ({value['low']}–{value['high']})"


def summary(runs: list[dict], metrics: tuple[str, ...]) -> dict:
    return {name: spread([run[name] for run in runs]) for name in metrics}


def in_order(versions: list, round_: int) -> list:
    """The order of one round: each round starts one version later (A B, B A, A B ...), so no
    version always runs first and a slow drift of the machine cancels out."""
    start = round_ % len(versions)
    return versions[start:] + versions[:start]


def growth(readings: list[float]) -> float:
    """Memory growth over the calls: readings[i] is taken after (i + 1) * EVERY calls."""
    return round(readings[-1] - readings[GROWTH_FROM // EVERY - 1], 3)


def peak_mb(ru_maxrss: int, system: str) -> float:
    """ru_maxrss is in KiB on Linux and in bytes on macOS."""
    return round(ru_maxrss * (1 if system == "Darwin" else 1024) / MB, 3)


def label_of(text: str) -> tuple[str, str | None, Path]:
    """`0.9.2=/venv/bin/kitden` or `main@f028492=/venv/bin/kitden`: label, commit, path."""
    label, _, path = text.partition("=")
    if not label or not path:
        raise ValueError(f"expected LABEL=KITDEN, got {text!r}")
    return label, (label.split("@", 1)[1] if "@" in label else None), Path(path).absolute()


def same_sample(a: dict, b: dict) -> bool:
    return a["page"]["sample"] == b["page"]["sample"]


def compare(a: dict, b: dict) -> tuple[list[str], list[str]]:
    """B against A on a night: (warnings, notes). Different samples are not compared."""
    if not same_sample(a, b):
        sa, sb = a["page"]["sample"], b["page"]["sample"]
        return [], [
            f"Not compared: the samples differ ({a['label']}: {sa['items']} items, "
            f"{sa['bytes']} bytes; {b['label']}: {sb['items']} items, {sb['bytes']} bytes)."
        ]
    warnings = []
    for name, share in WARN.items():
        sa, sb = a["page"]["summary"][name], b["page"]["summary"][name]
        was, now = sa["median"], sb["median"]
        if was > 0 and now > was * (1 + share):
            warnings.append(
                f"{b['label']} {NAMES[name]}: {_cell(sb)} against {_cell(sa)} for {a['label']}, "
                f"{round((now / was - 1) * 100)}% more by median (warns above "
                f"{round(share * 100)}%)."
            )
    return warnings, []


def broken_limits(result: dict) -> list[str]:
    """The limits B is over on a night (B is the last version). None of them on a backfill."""
    if result["kind"] != "night":
        return []
    b = result["versions"][-1]
    broken = []
    for name, limit in PAGE_LIMITS.items():
        value = b["page"]["summary"][name]
        if limit is not None and value["median"] > limit:
            broken.append(f"{b['label']} page {NAMES[name]}: {_cell(value)}, median over {limit}.")
    return broken


def cutoff(files: list[dict]) -> str:
    """For `uv pip install --exclude-newer`: one hour after the release's first upload, so the
    release itself is found and its dependencies are those of its day."""
    first = min(datetime.fromisoformat(f["upload_time_iso_8601"]) for f in files)
    return (first + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")


def check(result: dict) -> int:
    lines = [f"::warning::{text}" for text in result["warnings"]]
    lines += [f"::notice::{text}" for text in result["notes"]]
    broken = broken_limits(result)
    lines += [f"::error::{text}" for text in broken]
    print("\n".join(lines) or "No warning.")
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a") as out:
            for text in result["warnings"] + result["notes"] + broken:
                out.write(f"- {text}\n")
    return 1 if broken else 0


def main(argv: list[str] | None = None) -> int:
    return 0


if __name__ == "__main__":
    sys.exit(main())
