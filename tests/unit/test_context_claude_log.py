"""Claude Code's last skill list, read from chat logs written into a sandbox home."""

import json
import os
import time
from pathlib import Path

from kitden.context.claude_log import SentList, Unreadable, last_claude_list


def list_entry(
    names,
    content,
    *,
    folder="/work/a",
    version="2.1.311",
    entrypoint="claude-desktop",
    sidechain=False,
    at="2026-11-09T10:00:00Z",
    **attachment,
):
    return {
        "type": "attachment",
        "timestamp": at,
        "version": version,
        "entrypoint": entrypoint,
        "cwd": folder,
        "isSidechain": sidechain,
        "attachment": {
            "type": "skill_listing",
            "isInitial": True,
            "skillCount": len(names),
            "names": names,
            "content": content,
            **attachment,
        },
    }


def assistant(model="claude-opus-5-5"):
    return {"type": "assistant", "message": {"model": model}}


def write_chat(home: Path, slug, name, entries, mtime, raw_tail=""):
    path = home / ".claude/projects" / slug / f"{name}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in entries) + raw_tail)
    os.utime(path, (mtime, mtime))
    return path


def test_reads_names_and_sent_text_from_the_last_full_list(tmp_path):
    first = list_entry(["a"], "- a: Old.", at="2026-11-08T09:00:00Z")
    second = list_entry(["a", "b"], "- a: Does A.\n- b")
    write_chat(
        tmp_path, "p", "chat", [first, assistant("claude-sonnet-4-6"), second, assistant()], 100
    )
    got = last_claude_list(tmp_path, None)
    assert got == SentList(
        client="claude_code",
        at="2026-11-09T10:00:00Z",
        version="2.1.311",
        surface="in the Claude app",
        model="claude-opus-5-5",
        folder="/work/a",
        skills=(("a", "Does A."), ("b", None)),
    )


def test_a_description_with_a_dash_line_stays_whole(tmp_path):
    entry = list_entry(["a", "b"], "- a: One.\n- not a skill\n- b: Two.")
    write_chat(tmp_path, "p", "chat", [entry], 100)
    assert last_claude_list(tmp_path, None).skills == (("a", "One.\n- not a skill"), ("b", "Two."))


def test_a_name_that_starts_another_name_is_not_mixed_up(tmp_path):
    entry = list_entry(["ab", "a"], "- ab: Long.\n- a: Short.")
    write_chat(tmp_path, "p", "chat", [entry], 100)
    assert last_claude_list(tmp_path, None).skills == (("ab", "Long."), ("a", "Short."))


def test_skips_subagent_logs_sidechains_and_runs_that_are_not_a_chat(tmp_path):
    plain = list_entry(["a"], "- a: Plain.")
    write_chat(tmp_path, "p", "chat", [plain], 100)
    sub = list_entry(["a"], "- a: Subagent.")
    write_chat(tmp_path, "p/chat/subagents", "agent", [sub], 200)
    side = list_entry(["a"], "- a: Side.", sidechain=True)
    write_chat(tmp_path, "p", "side", [side], 300)
    sdk = list_entry(["a"], "- a: Run.", entrypoint="sdk-cli")
    write_chat(tmp_path, "p", "run", [sdk], 400)
    assert last_claude_list(tmp_path, None).skills == (("a", "Plain."),)


def test_an_unknown_entrypoint_is_read_without_a_surface(tmp_path):
    entry = list_entry(["a"], "- a: Hi.", entrypoint="claude-vscode")
    write_chat(tmp_path, "p", "chat", [entry], 100)
    got = last_claude_list(tmp_path, None)
    assert got.surface is None
    assert got.skills == (("a", "Hi."),)


def test_the_terminal_surface_is_named(tmp_path):
    write_chat(tmp_path, "p", "chat", [list_entry(["a"], "- a: Hi.", entrypoint="cli")], 100)
    assert last_claude_list(tmp_path, None).surface == "in the terminal"


def test_a_chat_with_no_list_yet_falls_back_to_the_next_older(tmp_path):
    write_chat(tmp_path, "p", "old", [list_entry(["a"], "- a: Old.")], 100)
    write_chat(tmp_path, "p", "new", [assistant()], 200)
    assert last_claude_list(tmp_path, None).skills == (("a", "Old."),)


def test_a_picked_folder_reads_only_its_own_chats(tmp_path):
    write_chat(tmp_path, "mine", "chat", [list_entry(["a"], "- a: Mine.", folder="/work/a")], 100)
    write_chat(tmp_path, "other", "chat", [list_entry(["a"], "- a: Other.", folder="/work/b")], 200)
    assert last_claude_list(tmp_path, "/work/a").skills == (("a", "Mine."),)
    assert last_claude_list(tmp_path, None).skills == (("a", "Other."),)
    assert last_claude_list(tmp_path, "/work/none") is None


def test_no_chats_at_all_is_none(tmp_path):
    assert last_claude_list(tmp_path, None) is None


def test_a_newer_version_with_an_unknown_shape_is_unreadable(tmp_path):
    write_chat(tmp_path, "p", "old", [list_entry(["a"], "- a: Old.")], 100)
    odd = list_entry(["a"], "- a: New.", version="2.2.0")
    del odd["attachment"]["names"]
    write_chat(tmp_path, "p", "new", [odd], 200)
    assert last_claude_list(tmp_path, None) == Unreadable("claude_code", "2.2.0")


def test_versions_compare_as_numbers(tmp_path):
    odd = list_entry(["a"], "- a: New.", version="2.1.1000")
    del odd["attachment"]["names"]
    write_chat(tmp_path, "p", "chat", [odd], 100)
    assert last_claude_list(tmp_path, None) == Unreadable("claude_code", "2.1.1000")


def test_an_odd_entry_from_a_known_version_is_skipped(tmp_path):
    write_chat(tmp_path, "p", "old", [list_entry(["a"], "- a: Old.")], 100)
    odd = list_entry(["a"], "- a: New.", isInitial=False)
    write_chat(tmp_path, "p", "new", [odd], 200)
    assert last_claude_list(tmp_path, None).skills == (("a", "Old."),)


def test_a_list_cut_short_is_not_a_full_list(tmp_path):
    write_chat(tmp_path, "p", "old", [list_entry(["a"], "- a: Old.")], 100)
    short = list_entry(["a"], "- a: New.", skillCount=3)
    write_chat(tmp_path, "p", "new", [short], 200)
    assert last_claude_list(tmp_path, None).skills == (("a", "Old."),)


def test_a_list_whose_names_are_not_all_text_is_not_a_full_list(tmp_path):
    write_chat(tmp_path, "p", "old", [list_entry(["a"], "- a: Old.")], 100)
    odd = list_entry(["a", 7], "- a: New.\n- 7: Seven.")
    write_chat(tmp_path, "p", "new", [odd], 200)
    assert last_claude_list(tmp_path, None).skills == (("a", "Old."),)


def test_a_half_written_last_line_is_skipped(tmp_path):
    entry = list_entry(["a"], "- a: Whole.")
    write_chat(
        tmp_path,
        "p",
        "chat",
        [entry],
        100,
        raw_tail='{"type": "attachment", "attachment": {"type": "skill_listing", "na',
    )
    assert last_claude_list(tmp_path, None).skills == (("a", "Whole."),)


def test_only_list_lines_are_parsed(tmp_path):
    path = tmp_path / ".claude/projects/p/big.jsonl"
    path.parent.mkdir(parents=True)
    other = json.dumps({"type": "user", "message": {"content": "x" * 200}})
    big = json.dumps(
        {
            "type": "assistant",
            "version": "2.1.311",
            "message": {"model": "claude-opus-5-5", "content": [{"text": "y" * 20_000}]},
        }
    )
    lines = [other] * 50_000 + [big] * 2_000
    lines.insert(25_000, json.dumps(list_entry(["a"], "- a: Hi.")))
    path.write_text("\n".join(lines) + "\n")
    start = time.perf_counter()
    got = last_claude_list(tmp_path, None)
    assert time.perf_counter() - start < 1
    assert got.skills == (("a", "Hi."),)
    assert got.model == "claude-opus-5-5"


def newer_chat(version="2.2.0", **fields):
    return {"type": "user", "version": version, "cwd": "/work/a", "isSidechain": False, **fields}


def test_a_newer_chat_with_no_list_is_unreadable_not_the_older_chat(tmp_path):
    write_chat(tmp_path, "p", "old", [list_entry(["a"], "- a: Old.")], 100)
    write_chat(tmp_path, "p", "new", [newer_chat(), assistant()], 200)
    assert last_claude_list(tmp_path, None) == Unreadable("claude_code", "2.2.0")


def test_a_known_version_chat_with_no_list_is_still_skipped(tmp_path):
    write_chat(tmp_path, "p", "old", [list_entry(["a"], "- a: Old.")], 100)
    write_chat(tmp_path, "p", "new", [newer_chat("2.1.311")], 200)
    assert last_claude_list(tmp_path, None).skills == (("a", "Old."),)


def test_a_newer_chat_that_is_not_a_person_chat_or_folder_is_skipped(tmp_path):
    write_chat(tmp_path, "p", "old", [list_entry(["a"], "- a: Old.")], 100)
    write_chat(tmp_path, "p", "sdk", [newer_chat(entrypoint="sdk-cli")], 200)
    write_chat(tmp_path, "p", "side", [newer_chat(isSidechain=True)], 300)
    write_chat(tmp_path, "p", "elsewhere", [newer_chat(cwd="/work/b")], 400)
    assert last_claude_list(tmp_path, "/work/a").skills == (("a", "Old."),)


def test_a_file_that_cannot_be_read_is_skipped(tmp_path):
    write_chat(tmp_path, "p", "ok", [list_entry(["a"], "- a: Fine.")], 100)
    (tmp_path / ".claude/projects/p/dir.jsonl").mkdir()  # opening it fails
    (tmp_path / ".claude/projects/p/gone.jsonl").symlink_to(tmp_path / "missing")  # stat fails
    assert last_claude_list(tmp_path, None).skills == (("a", "Fine."),)


def test_a_list_with_no_entrypoint_is_read_without_a_surface(tmp_path):
    entry = list_entry(["a"], "- a: Hi.")
    del entry["entrypoint"]
    write_chat(tmp_path, "p", "chat", [entry], 100)
    got = last_claude_list(tmp_path, None)
    assert got.surface is None
    assert got.skills == (("a", "Hi."),)


def test_a_list_with_no_version_has_an_empty_version(tmp_path):
    entry = list_entry(["a"], "- a: Hi.")
    del entry["version"]
    write_chat(tmp_path, "p", "chat", [entry], 100)
    assert last_claude_list(tmp_path, None).version == ""
