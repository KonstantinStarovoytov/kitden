"""Claude Code's last skill list, read from chat logs written into a sandbox home."""

import json
import os
import time
from datetime import datetime
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


def stamp(at: str) -> float:
    return datetime.fromisoformat(at).timestamp()


def test_the_newest_list_wins_not_the_newest_file(tmp_path):
    # An old chat's file can change later with no new list (the app touched it).
    old = list_entry(["a"], "- a: Old.", at="2026-10-26T19:00:00Z")
    new = list_entry(["a"], "- a: New.", at="2026-11-11T23:00:00Z")
    write_chat(tmp_path, "p", "old", [old], stamp("2026-11-12T17:10:00Z"))
    write_chat(tmp_path, "p", "new", [new], stamp("2026-11-11T23:05:00Z"))
    got = last_claude_list(tmp_path, None)
    assert (got.at, got.skills) == ("2026-11-11T23:00:00Z", (("a", "New."),))


def test_a_newer_unreadable_list_wins_over_an_older_good_one(tmp_path):
    good = list_entry(["a"], "- a: Old.", at="2026-11-10T09:00:00Z")
    odd = list_entry("a", "- a: New.", at="2026-11-11T09:00:00Z")
    write_chat(tmp_path, "p", "good", [good], stamp("2026-11-12T09:00:00Z"))
    write_chat(tmp_path, "p", "odd", [odd], stamp("2026-11-11T09:05:00Z"))
    assert isinstance(last_claude_list(tmp_path, None), Unreadable)


def test_a_picked_folder_reads_only_its_own_chats(tmp_path):
    write_chat(tmp_path, "mine", "chat", [list_entry(["a"], "- a: Mine.", folder="/work/a")], 100)
    write_chat(tmp_path, "other", "chat", [list_entry(["a"], "- a: Other.", folder="/work/b")], 200)
    assert last_claude_list(tmp_path, "/work/a").skills == (("a", "Mine."),)
    assert last_claude_list(tmp_path, None).skills == (("a", "Other."),)
    assert last_claude_list(tmp_path, "/work/none") is None


def test_no_chats_at_all_is_none(tmp_path):
    assert last_claude_list(tmp_path, None) is None


def test_a_list_with_an_unknown_shape_is_unreadable_on_any_version(tmp_path):
    for version in ("2.0.5", "2.1.311", "9.9.9"):
        write_chat(tmp_path, "p", "old", [list_entry(["a"], "- a: Old.")], 100)
        odd = list_entry(["a"], "- a: New.", version=version)
        del odd["attachment"]["names"]
        write_chat(tmp_path, "p", "new", [odd], 200)
        assert last_claude_list(tmp_path, None) == Unreadable("claude_code", version)


def test_a_good_list_after_an_odd_one_is_read(tmp_path):
    odd = list_entry(["a"], "- a: Odd.")
    del odd["attachment"]["content"]
    write_chat(tmp_path, "p", "chat", [odd, list_entry(["a"], "- a: Good.")], 100)
    assert last_claude_list(tmp_path, None).skills == (("a", "Good."),)


def test_added_skills_alone_fall_back_to_the_next_older(tmp_path):
    write_chat(tmp_path, "p", "old", [list_entry(["a"], "- a: Old.")], 100)
    odd = list_entry(["a"], "- a: New.", isInitial=False)
    write_chat(tmp_path, "p", "new", [odd], 200)
    assert last_claude_list(tmp_path, None).skills == (("a", "Old."),)


def test_skills_added_during_a_chat_are_marked_until_the_next_full_list(tmp_path):
    # Claude Code sends an added skill with its description whatever the limit, so the rule
    # must not count it (checked 2026-11-12, real log of Claude Code 2.1.309).
    first = list_entry(["a"], "- a")
    more = list_entry(["c"], "- c: Does C.", isInitial=False, at="2026-11-09T11:00:00Z")
    write_chat(tmp_path, "p", "chat", [first, more], 100)
    got = last_claude_list(tmp_path, None)
    assert (got.skills, got.added) == ((("a", None), ("c", "Does C.")), frozenset({"c"}))
    again = list_entry(["a", "c"], "- a\n- c", at="2026-11-09T12:00:00Z")
    write_chat(tmp_path, "p", "chat", [first, more, again], 100)
    assert last_claude_list(tmp_path, None).added == frozenset()


def test_a_list_cut_short_is_not_a_full_list(tmp_path):
    write_chat(tmp_path, "p", "old", [list_entry(["a"], "- a: Old.")], 100)
    short = list_entry(["a"], "- a: New.", skillCount=3)
    write_chat(tmp_path, "p", "new", [short], 200)
    assert last_claude_list(tmp_path, None).skills == (("a", "Old."),)


def test_a_list_whose_names_are_not_all_text_is_unreadable(tmp_path):
    write_chat(tmp_path, "p", "old", [list_entry(["a"], "- a: Old.")], 100)
    odd = list_entry(["a", 7], "- a: New.\n- 7: Seven.")
    write_chat(tmp_path, "p", "new", [odd], 200)
    assert last_claude_list(tmp_path, None) == Unreadable("claude_code", "2.1.311")


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


def test_a_chat_with_no_list_falls_back_whatever_its_version(tmp_path):
    for version in ("2.0.5", "9.9.9"):
        write_chat(tmp_path, "p", "old", [list_entry(["a"], "- a: Old.")], 100)
        bare = {"type": "user", "version": version, "cwd": "/work/a", "isSidechain": False}
        write_chat(tmp_path, "p", "new", [bare, assistant()], 200)
        assert last_claude_list(tmp_path, None).skills == (("a", "Old."),)


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


def added_entry(names, content, **kw):
    """A list of skills added in the middle of a chat."""
    return list_entry(names, content, isInitial=False, **kw)


def test_skills_added_in_the_middle_of_a_chat_join_the_list(tmp_path):
    full = list_entry(["a", "b"], "- a: Does A.\n- b", at="2026-11-09T10:00:00Z")
    added = added_entry(["p:c"], "- p:c: Does C.", at="2026-11-09T11:00:00Z")
    write_chat(tmp_path, "p", "chat", [full, assistant(), added], 100)
    got = last_claude_list(tmp_path, None)
    assert got.skills == (("a", "Does A."), ("b", None), ("p:c", "Does C."))
    assert got.at == "2026-11-09T11:00:00Z"


def test_an_added_skill_already_in_the_list_takes_its_new_text(tmp_path):
    full = list_entry(["a", "b"], "- a\n- b: Does B.")
    write_chat(tmp_path, "p", "chat", [full, added_entry(["a"], "- a: Does A.")], 100)
    assert last_claude_list(tmp_path, None).skills == (("a", "Does A."), ("b", "Does B."))


def test_a_full_list_after_added_skills_stands_alone(tmp_path):
    full = list_entry(["a"], "- a: Does A.")
    again = list_entry(["a", "c"], "- a: Does A.\n- c")
    write_chat(tmp_path, "p", "chat", [full, added_entry(["c"], "- c: Does C."), again], 100)
    assert last_claude_list(tmp_path, None).skills == (("a", "Does A."), ("c", None))


def test_added_skills_with_no_full_list_before_them_are_no_list(tmp_path):
    write_chat(tmp_path, "p", "chat", [added_entry(["c"], "- c: Does C."), assistant()], 100)
    assert last_claude_list(tmp_path, None) is None


def test_added_skills_from_another_version_keep_the_list_readable(tmp_path):
    full = list_entry(["a"], "- a: Does A.", version="2.2.0")
    added = added_entry(["c"], "- c: Does C.", version="2.2.0")
    write_chat(tmp_path, "p", "chat", [full, added], 100)
    assert last_claude_list(tmp_path, None).skills == (("a", "Does A."), ("c", "Does C."))


def test_the_model_is_the_one_that_answered_the_list_not_a_later_one(tmp_path):
    entries = [
        assistant("claude-sonnet-4-6"),
        list_entry(["a"], "- a: Does A."),
        assistant("claude-fable-5-1"),
        assistant("claude-opus-5-5"),
    ]
    write_chat(tmp_path, "p", "chat", entries, 100)
    assert last_claude_list(tmp_path, None).model == "claude-fable-5-1"


def test_a_list_with_no_answer_yet_takes_the_model_before_it(tmp_path):
    entries = [assistant("claude-sonnet-4-6"), list_entry(["a"], "- a: Does A.")]
    write_chat(tmp_path, "p", "chat", entries, 100)
    assert last_claude_list(tmp_path, None).model == "claude-sonnet-4-6"
