"""Measure the CPU and memory a `kitden` command uses, from outside, so any release since 0.3.0
can be measured the same way (docs/development.md, CPU and memory).

    run --out FILE [--runs 5] [--backfill] [--run-id ID] [--gateway PYTHON] LABEL=KITDEN ...
    check FILE          print the warnings; exit 1 when a limit is broken
    store FILE DATA     put FILE into the data folder (nights/, releases/, chart.json),
                        rebuild DATA/README.md
    report DATA         rebuild DATA/README.md only
    cutoff VERSION PYPI_JSON   the --exclude-newer time for a release: its upload + 1 hour

LABEL is a release version (`0.9.2`) or `main@<commit>`; KITDEN is the `kitden` of a plain venv.
A night gives two: the newest release (A), then this commit (B). `--backfill` takes any number of
releases and compares nothing. Every version gets one warm-up run, thrown away, then `--runs`
runs, in turn, each round starting one version later (A B, B A, A B ...). `--gateway PYTHON`
adds the gateway scenario, with the test echo servers run by PYTHON (the checkout's own, which
has `mcp`); its rounds come after all the page's.

Standard library only, plus psutil for `run`
(`uv run --no-project --python 3.13 --with psutil==7.2.2`). It imports nothing of Kitden: it
must run against old releases. Never run it on the real home folder: every run gets a sandbox
HOME and temp folder of its own.
"""

import argparse
import contextlib
import http.client
import json
import os
import platform
import re
import selectors
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

# One series number per scenario. Raise a scenario's number with any change to what or how it
# is measured. Numbers of two series are never compared or drawn together; a new page series
# needs a new backfill.
SERIES = {"page": 1, "gateway": 1}
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
GATEWAY_LIMITS: dict[str, float | None] = {"idle_cpu_s": None, "growth_mb": None}
PAGE_METRICS = ("peak_mb", "cpu_ready_s", "idle_cpu_s", "growth_mb", "ready_s")
GATEWAY_METRICS = ("cpu_ready_s", "idle_cpu_s", "calls_cpu_s", "growth_mb", "ready_s")
NAMES = {
    "peak_mb": "peak memory (MB)",
    "cpu_ready_s": "CPU to ready (s)",
    "idle_cpu_s": "idle CPU in 30 s (s)",
    "growth_mb": "memory growth over the calls (MB)",
    "calls_cpu_s": "CPU of the calls (s)",
    "ready_s": "time to ready (s), not compared",
}
CHARTED = ("peak_mb", "cpu_ready_s")  # chart.json: the desk page's two charts, by release
NIGHTS_SHOWN = 14
ECHO = Path(__file__).resolve().parents[1] / "tests/fixtures/fake_mcp/echo_server.py"
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
    varied = [v["label"] for v in (a, b) if v["page"]["sample"]["varies"]]
    if varied:
        return [], [f"Not compared: the sample changed between runs of {' and '.join(varied)}."]
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
    for scenario, limits in (("page", PAGE_LIMITS), ("gateway", GATEWAY_LIMITS)):
        for name, limit in limits.items():
            if limit is None or scenario not in b:
                continue
            value = b[scenario]["summary"][name]
            if value["median"] > limit:
                broken.append(
                    f"{b['label']} {scenario} {NAMES[name]}: {_cell(value)}, median over {limit}."
                )
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


def release_file(result: dict, version: dict) -> dict:
    # On a backfill the release files are the record, so they keep how the runs were done.
    keys = ("series", "kind", "run_id", "date", "time", "warm", "warmup_runs", "runs_each")
    gateway = {"gateway_rounds": result["gateway_rounds"]} if "gateway_rounds" in result else {}
    return {**{k: result[k] for k in (*keys, "rounds", "env")}, **gateway, "version": version}


def _plain(text: str, pattern: str, what: str) -> None:
    """A value that becomes a file name in the data folder, in a job that holds a write token."""
    if not re.fullmatch(pattern, text):
        raise SystemExit(f"store: refused the {what} {text!r}: it must match {pattern}.")


def store(result: dict, data: Path) -> list[Path]:
    """Write a result into the data folder. A night: nights/<date>.json, and A's release file
    when it is missing. A backfill: every release file, overwritten."""
    _plain(result["kind"], r"night|backfill", "kind")
    night = result["kind"] == "night"
    # A night's release is A; on a backfill, this commit is no release: it goes only into the chart.
    releases = (
        result["versions"][:1] if night else [v for v in result["versions"] if not v["commit"]]
    )
    _plain(result["date"], r"[0-9]{4}-[0-9]{2}-[0-9]{2}", "date")
    for version in releases:
        _plain(version["label"], r"[0-9A-Za-z.-]+", "release label")
    written = []

    def write(path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=1) + "\n")
        written.append(path)

    if night:
        write(data / "nights" / f"{result['date']}.json", result)
        a = releases[0]
        path = data / "releases" / f"{a['label']}.json"
        if not path.exists():
            write(path, release_file(result, a))
    else:
        for version in releases:
            write(data / "releases" / f"{version['label']}.json", release_file(result, version))
        write(data / "chart.json", chart(result))
    (data / "README.md").write_text(readme(data))
    written.append(data / "README.md")
    return written


def _key(version: str) -> tuple:
    return tuple(int(part) for part in re.findall(r"\d+", version))


def _read(folder: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))]


def chart(result: dict) -> dict:
    """What the desk page draws (kitden-sdlc reads chart.json), from one backfill run only: one
    machine, one day (B0 rule 8). Its releases by version, then this commit as "main"."""
    releases = sorted(
        (v for v in result["versions"] if not v["commit"]), key=lambda v: _key(v["label"])
    )
    commits = [v for v in result["versions"] if v["commit"]]
    return {
        "series": result["series"]["page"],
        "run_id": result["run_id"],
        "date": result["date"],
        "cpu": result["env"]["cpu"],
        "runs": result["runs_each"],
        "points": [
            {
                "label": "main" if v["commit"] else v["label"],
                "commit": v["commit"],
                **{name: v["page"]["summary"][name] for name in CHARTED},
            }
            for v in releases + commits
        ],
    }


def readme(data: Path) -> str:
    """The data branch's README: the releases and the last nights of main, as tables. Only
    the newest series is shown. The charts are on the desk page (chart.json)."""
    nights, releases = _read(data / "nights"), _read(data / "releases")
    series = max((f["series"]["page"] for f in nights + releases), default=SERIES["page"])
    nights = sorted((f for f in nights if f["series"]["page"] == series), key=lambda f: f["date"])
    releases = sorted(
        (f for f in releases if f["series"]["page"] == series),
        key=lambda f: _key(f["version"]["label"]),
    )
    out = [
        "# CPU and memory of Kitden",
        "",
        "Written by `.github/workflows/use.yml` on `main`; how it measures is in "
        "`docs/development.md` (CPU and memory). Each cell is the median, then the lowest and "
        f"highest run. Page series {series}: numbers of another series are not shown.",
        "",
        "## Releases",
        "",
        "A backfill installs each release with the dependencies of its release day; a night "
        "installs the newest release with that night's newest dependencies. CPU seconds depend "
        "on the CPU, so compare rows of one CPU model.",
        "",
        "| Version | Peak memory (MB) | CPU to ready (s) | Idle CPU in 30 s (s) "
        "| Growth (MB) | Sample (items, bytes) | CPU | Measured |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for f in releases:
        page = f["version"]["page"]
        s = page["summary"]
        out.append(
            f"| {f['version']['label']} | {_cell(s['peak_mb'])} | {_cell(s['cpu_ready_s'])} "
            f"| {_cell(s['idle_cpu_s'])} | {_cell(s['growth_mb'])} "
            f"| {page['sample']['items']}, {page['sample']['bytes']} | {f['env']['cpu']} "
            f"| {f['kind']} {f['date']} |"
        )
    out += [
        "",
        "Charts of peak memory and CPU to ready by release: "
        "https://konstantinstarovoytov.github.io/kitden-sdlc/desk/#use",
    ]
    out += [
        "",
        f"## The last {NIGHTS_SHOWN} nights",
        "",
        "A is the newest release, B is `main` that night, measured in turn in the same job.",
        "",
        "| Night | A | B | Peak A | Peak B | CPU to ready A | CPU to ready B "
        "| Idle CPU B | Growth B | Gateway idle CPU B | Gateway growth B | Notes |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    # Gateway cells only of the newest gateway series.
    gateway_series = max((f["series"].get("gateway", 0) for f in nights), default=0)
    for f in nights[-NIGHTS_SHOWN:][::-1]:
        a, b = f["versions"]
        sa, sb = a["page"]["summary"], b["page"]["summary"]
        same = f["series"].get("gateway") == gateway_series
        gate = b.get("gateway", {}).get("summary") if same else None
        notes = " ".join(f["warnings"] + f["notes"]) or "—"
        out.append(
            f"| {f['date']} | {a['label']} | {b['label']} | {_cell(sa['peak_mb'])} "
            f"| {_cell(sb['peak_mb'])} | {_cell(sa['cpu_ready_s'])} | {_cell(sb['cpu_ready_s'])} "
            f"| {_cell(sb['idle_cpu_s'])} | {_cell(sb['growth_mb'])} "
            f"| {_cell(gate['idle_cpu_s']) if gate else '—'} "
            f"| {_cell(gate['growth_mb']) if gate else '—'} | {notes} |"
        )
    return "\n".join(out) + "\n"


# --- Measuring (run against real releases; see docs/development.md) ---


def _tree(proc) -> list:
    import psutil

    try:
        return [proc, *proc.children(recursive=True)]
    except psutil.Error:
        return [proc]


def _rss_mb(proc) -> float:
    import psutil

    total = 0
    for p in _tree(proc):
        with contextlib.suppress(psutil.Error):
            total += p.memory_info().rss
    return round(total / MB, 3)


def _cpu(proc, exited: bool = False) -> float:
    """CPU seconds (user and system) of the process and its live descendants. With exited=True
    (the gateway), also of descendants that ended and were collected by their parent in the
    tree, so a server that ends between two readings is not lost: Linux counts them in
    children_user and children_system; macOS reports 0 there, so it loses them. The page keeps
    the plain sum it was measured with in its series 1 (its demo starts no child)."""
    import psutil

    total = 0.0
    for p in _tree(proc):
        with contextlib.suppress(psutil.Error):
            times = p.cpu_times()
            total += times.user + times.system
            if exited:
                total += getattr(times, "children_user", 0.0)
                total += getattr(times, "children_system", 0.0)
    return total


def _sandbox(root: Path) -> dict:
    """A fresh HOME and temp folder, at the same paths every run, so every run's sample has
    paths of the same length."""
    for name in ("home", "tmp"):
        shutil.rmtree(root / name, ignore_errors=True)
        (root / name).mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("KITDEN_", "XDG_"))}
    return {**env, "HOME": str(root / "home"), "TMPDIR": str(root / "tmp")}


def _stop(child: subprocess.Popen, term: bool = True) -> int:
    """SIGTERM (or, with term=False, only wait for the child to end by itself), then collect
    it with wait4; SIGKILL after STOP_SECONDS. Then SIGKILL what is left of its process group,
    so nothing it started outlives the run. Returns its ru_maxrss."""
    if term:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGTERM)
    deadline = time.monotonic() + STOP_SECONDS
    while time.monotonic() < deadline:
        pid, status, usage = os.wait4(child.pid, os.WNOHANG)
        if pid:
            break
        time.sleep(0.05)
    else:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGKILL)
        _, status, usage = os.wait4(child.pid, 0)
    child.returncode = os.waitstatus_to_exitcode(status)
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(child.pid, signal.SIGKILL)
    return usage.ru_maxrss


def page_run(kitden: Path, root: Path) -> dict:
    """One run of the page scenario (docs/development.md, CPU and memory)."""
    import psutil

    start = time.monotonic()
    child = subprocess.Popen(  # noqa: S603 - the kitden under test, fixed arguments
        [str(kitden), "demo", "--no-browser", "--size", "large"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=_sandbox(root),
        cwd=root / "home",
        start_new_session=True,
    )
    try:
        assert child.stdout is not None
        proc = psutil.Process(child.pid)
        # A release that never prints its link must not hang the job.
        with selectors.DefaultSelector() as waiting:
            waiting.register(child.stdout, selectors.EVENT_READ)
            if not waiting.select(GIVE_UP_SECONDS):
                raise RuntimeError("kitden demo printed no link")
        found = LINK.search(child.stdout.readline())
        if not found:
            raise RuntimeError("kitden demo printed no link")
        port, token = int(found[2]), found[3]
        # The link is printed before the port listens.
        while True:
            try:
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
                conn.request("GET", f"/?token={token}")
                answer = conn.getresponse()
                answer.read()
                break
            except ConnectionRefusedError:
                if time.monotonic() - start > GIVE_UP_SECONDS:
                    raise
                time.sleep(0.02)
        cookie = {"Cookie": answer.getheader("set-cookie", "").split(";")[0]}

        def get(path: str) -> bytes:
            conn.request("GET", path, headers=cookie)
            reply = conn.getresponse()
            body = reply.read()
            if reply.status != 200:
                raise RuntimeError(f"{path} answered {reply.status}")
            return body

        cpu_ready = ready = None
        while True:
            progress = json.loads(get("/api/progress"))
            if progress["ready"] and ready is None:
                ready, cpu_ready = time.monotonic() - start, _cpu(proc)
            if progress["ready"] and all(step["done"] for step in progress["steps"]):
                break
            if time.monotonic() - start > GIVE_UP_SECONDS:
                raise RuntimeError("the first scan did not end")
            time.sleep(0.1)
        before = _cpu(proc)
        time.sleep(IDLE_SECONDS)
        idle = _cpu(proc) - before
        conn.close()  # the server drops a connection left idle this long
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
        readings, body = [], b""
        for call in range(1, CALLS + 1):
            body = get("/api/items")
            if call % EVERY == 0:
                readings.append(_rss_mb(proc))
        conn.close()
    finally:
        maxrss = _stop(child)
    assert ready is not None and cpu_ready is not None
    return {
        "ready_s": round(ready, 3),
        "cpu_ready_s": round(cpu_ready, 3),
        "idle_cpu_s": round(idle, 3),
        "memory_mb": readings,
        "growth_mb": growth(readings),
        "peak_mb": peak_mb(maxrss, platform.system()),
        "sample": {"items": len(json.loads(body)), "bytes": len(body)},
        "exit": child.returncode,
    }


def _data_dir(home: Path) -> Path:
    if platform.system() == "Darwin":
        return home / "Library/Application Support/kitden"
    return home / ".local/share/kitden"


def gateway_run(kitden: Path, root: Path, python: Path) -> dict:
    """One run of the gateway scenario: `kitden mcp` with three echo servers, spoken to by hand
    (docs/development.md, CPU and memory)."""
    import psutil

    env = _sandbox(root)
    home = root / "home"
    servers = {name: {"command": str(python), "args": [str(ECHO), name]} for name in "abc"}
    _data_dir(home).mkdir(parents=True)
    (_data_dir(home) / "gateway.json").write_text(json.dumps({"servers": servers, "rules": {}}))
    start = time.monotonic()
    child = subprocess.Popen(  # noqa: S603 - the kitden under test, fixed arguments
        [str(kitden), "mcp", "--home", str(home)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=env,
        cwd=home,
        start_new_session=True,
    )
    stdin, stdout = child.stdin, child.stdout
    assert stdin is not None and stdout is not None
    sent = [0]
    seen: list = []  # the tree, last read: the echo servers are ended with it

    def give_up(_signal: int, _frame: object) -> None:
        raise TimeoutError("kitden mcp stopped answering")

    def call(method: str, params: dict | None = None) -> dict:
        sent[0] += 1
        message = {"jsonrpc": "2.0", "id": sent[0], "method": method, "params": params or {}}
        stdin.write(json.dumps(message) + "\n")
        stdin.flush()
        while True:
            line = stdout.readline()
            if not line:
                raise RuntimeError("kitden mcp closed its output")
            answer = json.loads(line)
            if answer.get("id") == sent[0]:
                return answer

    # A gateway that stops answering must not hang the job: an alarm in this process.
    signal.signal(signal.SIGALRM, give_up)
    signal.alarm(GIVE_UP_SECONDS + IDLE_SECONDS)
    try:
        proc = psutil.Process(child.pid)
        call(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "measure-use", "version": str(SERIES["gateway"])},
            },
        )
        stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        stdin.flush()
        tools = call("tools/list")["result"]["tools"]
        ready, cpu_ready = time.monotonic() - start, _cpu(proc, exited=True)
        seen = _tree(proc)
        before = _cpu(proc, exited=True)
        time.sleep(IDLE_SECONDS)
        idle = _cpu(proc, exited=True) - before
        readings, before = [], _cpu(proc, exited=True)
        for number in range(1, CALLS + 1):
            call("tools/list")
            if number % EVERY == 0:
                readings.append(_rss_mb(proc))
        calls = _cpu(proc, exited=True) - before
        seen = _tree(proc)
        processes = len(seen)
    finally:
        signal.alarm(0)
        with contextlib.suppress(OSError):
            stdin.close()
        _stop(child, term=False)  # a closed input ends kitden mcp
        # The mcp client starts each server in a session of its own, out of reach of the group
        # kill in _stop: end any server that kitden mcp left.
        for p in seen[1:]:
            with contextlib.suppress(psutil.Error):
                p.kill()
    return {
        "ready_s": round(ready, 3),
        "cpu_ready_s": round(cpu_ready, 3),
        "idle_cpu_s": round(idle, 3),
        "calls_cpu_s": round(calls, 3),
        "memory_mb": readings,
        "growth_mb": growth(readings),
        "tools": len(tools),
        "processes": processes,
        "exit": child.returncode,
    }


def packages(kitden: Path) -> dict:
    """The Python and every installed package of the venv that holds this `kitden`."""
    code = (
        "import importlib.metadata as m, json, platform; print(json.dumps({'python': "
        "platform.python_version(), 'packages': sorted(f\"{d.metadata['Name']}=="
        '{d.version}" for d in m.distributions())}))'
    )
    found = subprocess.run(  # noqa: S603 - the venv's own Python, fixed code
        [str(kitden.with_name("python")), "-I", "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(found.stdout)


def _cpu_model() -> str:
    if platform.system() == "Darwin":
        found = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True
        )
        return found.stdout.strip() or "unknown"
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def environment() -> dict:
    import psutil

    return {
        # GitHub's runners name their image in these two variables.
        "runner_image": os.environ.get("ImageOS", "local"),  # noqa: SIM112
        "image_version": os.environ.get("ImageVersion", "local"),  # noqa: SIM112
        "system": platform.platform(),
        "cpu": _cpu_model(),
        "cores": os.cpu_count(),
        "python": platform.python_version(),
        "psutil": psutil.__version__,
    }


def measure(args: argparse.Namespace) -> dict:
    labels = [label_of(text)[0] for text in args.versions]
    if len(set(labels)) != len(labels):
        raise SystemExit("Each version needs its own label.")
    versions = []
    for text in args.versions:
        label, commit, kitden = label_of(text)
        installed = packages(kitden)
        own = next((p for p in installed["packages"] if p.lower().startswith("kitden==")), None)
        if own is None:
            raise SystemExit(f"{kitden} is not in a venv that has kitden installed.")
        versions.append(
            {
                "label": label,
                "commit": commit,
                "kitden": own.split("==", 1)[1],
                "path": kitden,
                **installed,
            }
        )
    if args.backfill and any(v["commit"] for v in versions[:-1]):
        raise SystemExit("A backfill measures releases, then at most this commit, last.")
    if not args.backfill and len(versions) != 2:
        raise SystemExit("A night measures two versions: the newest release, then this commit.")
    now = datetime.now(UTC)
    # Round 0 is the warm-up, thrown away. Each round starts one version later. The order is
    # fixed here and kept in the result, so the result shows the order that ran. The gateway's
    # rounds come after all the page's, so the page is measured the same way with or without.
    rounds = [[v["label"] for v in in_order(versions, r)] for r in range(WARMUP + args.runs)]
    scenarios = ["page", "gateway"] if args.gateway else ["page"]
    by_label = {v["label"]: v for v in versions}
    root = Path(tempfile.mkdtemp(prefix="measure-use-")).resolve()
    kept: dict[str, dict[str, list]] = {s: {v["label"]: [] for v in versions} for s in scenarios}
    try:
        for scenario in scenarios:
            for round_, labels in enumerate(rounds):
                for label in labels:
                    kitden = by_label[label]["path"]
                    if scenario == "page":
                        one = page_run(kitden, root)
                    else:
                        one = gateway_run(kitden, root, Path(args.gateway))
                    print(f"{scenario} {round_} {label}: {json.dumps(one)}", file=sys.stderr)
                    if round_ >= WARMUP:
                        kept[scenario][label].append(one)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    for v in versions:
        runs = kept["page"][v["label"]]
        samples = {json.dumps(run["sample"]) for run in runs}
        v["page"] = {
            # The sample of the first run; "varies" when the runs did not all see the same one.
            "sample": {**runs[0]["sample"], "varies": len(samples) > 1},
            "summary": summary(runs, PAGE_METRICS),
            "runs": runs,
        }
        if args.gateway:
            runs = kept["gateway"][v["label"]]
            v["gateway"] = {"summary": summary(runs, GATEWAY_METRICS), "runs": runs}
        v["path"] = str(v["path"])
    result = {
        "series": {s: SERIES[s] for s in scenarios},
        "kind": "backfill" if args.backfill else "night",
        "run_id": args.run_id,
        "date": now.date().isoformat(),
        "time": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "warm": True,
        "warmup_runs": WARMUP,
        "runs_each": args.runs,
        "rounds": rounds,
        **({"gateway_rounds": rounds} if args.gateway else {}),
        "env": environment(),
        "versions": versions,
        "warnings": [],
        "notes": [],
    }
    if not args.backfill:
        result["warnings"], result["notes"] = compare(*versions)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    modes = parser.add_subparsers(dest="mode", required=True)
    run = modes.add_parser("run")
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--runs", type=int, default=5)
    run.add_argument("--backfill", action="store_true")
    run.add_argument("--run-id", default="local")
    run.add_argument("--gateway", metavar="PYTHON")
    run.add_argument("versions", nargs="+", metavar="LABEL=KITDEN")
    modes.add_parser("check").add_argument("file", type=Path)
    put = modes.add_parser("store")
    put.add_argument("file", type=Path)
    put.add_argument("data", type=Path)
    modes.add_parser("report").add_argument("data", type=Path)
    when = modes.add_parser("cutoff")
    when.add_argument("version")
    when.add_argument("pypi", type=Path)
    args = parser.parse_args(argv)
    if args.mode == "run":
        result = measure(args)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=1) + "\n")
        return 0
    if args.mode == "check":
        return check(json.loads(args.file.read_text()))
    if args.mode == "store":
        for path in store(json.loads(args.file.read_text()), args.data):
            print(path)
        return 0
    if args.mode == "report":
        (args.data / "README.md").write_text(readme(args.data))
        return 0
    print(cutoff(json.loads(args.pypi.read_text())["releases"][args.version]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
