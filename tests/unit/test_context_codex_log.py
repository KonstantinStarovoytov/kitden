"""Codex's last skill list and window, read from logs written into a sandbox codex home."""

import json
import os
import time
from datetime import datetime
from pathlib import Path

from kitden.context.claude_log import SentList, Unreadable
from kitden.context.codex_log import CodexSent, codex_window, codex_windows, last_codex_list

LIST = (
    "<skills_instructions>\n"
    "- a: Does A. (file: /s/a/SKILL.md)\n"
    "- b: (file: /s/b/SKILL.md)\n"
    "</skills_instructions>"
)


def meta(folder="/work/a", version="0.163.0-alpha.11", source="user"):
    payload = {
        "timestamp": "2026-11-08T08:00:00Z",
        "cwd": folder,
        "thread_source": source,
        "cli_version": version,
    }
    return {"type": "session_meta", "payload": payload}


def turn(model="gpt-6-astra"):
    return {"type": "turn_context", "payload": {"model": model}}


def skills(text=LIST, at="2026-11-09T10:00:00Z", role="developer"):
    content = [{"type": "input_text", "text": text}]
    payload = {"type": "message", "role": role, "content": content}
    return {"timestamp": at, "type": "response_item", "payload": payload}


def write_log(home: Path, name, entries, mtime, raw_tail="", day="2026/11/08"):
    path = home / "sessions" / day / f"rollout-{name}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in entries) + raw_tail)
    os.utime(path, (mtime, mtime))
    return path


def test_reads_each_line_with_its_path(tmp_path):
    write_log(tmp_path, "a", [meta(), turn(), skills()], 100)
    got = last_codex_list(tmp_path, None)
    assert got == CodexSent(
        list=SentList(
            client="codex",
            at="2026-11-09T10:00:00Z",
            version="0.163.0-alpha.11",
            surface=None,
            model="gpt-6-astra",
            folder="/work/a",
            skills=(("a", "Does A."), ("b", "")),
        ),
        paths={"a": "/s/a/SKILL.md", "b": "/s/b/SKILL.md"},
        shown={"a": "/s/a/SKILL.md", "b": "/s/b/SKILL.md"},
        roots=(),
    )
    assert got.paths["b"] == "/s/b/SKILL.md"


def test_a_description_with_a_colon_keeps_it(tmp_path):
    text = "<skills_instructions>\n- a: Use: when X. (file: /p)\n</skills_instructions>"
    write_log(tmp_path, "a", [meta(), skills(text)], 100)
    assert last_codex_list(tmp_path, None).list.skills == (("a", "Use: when X."),)


def test_a_plugin_skill_keeps_its_prefix(tmp_path):
    text = (
        "<skills_instructions>\n"
        "- plugin:skill: Does B. (file: /p/b/SKILL.md)\n"
        "- plugin:other: (file: /p/o/SKILL.md)\n"
        "</skills_instructions>"
    )
    write_log(tmp_path, "a", [meta(), skills(text)], 100)
    got = last_codex_list(tmp_path, None)
    assert got.list.skills == (("plugin:skill", "Does B."), ("plugin:other", ""))
    assert got.paths == {"plugin:skill": "/p/b/SKILL.md", "plugin:other": "/p/o/SKILL.md"}


def test_a_name_may_have_spaces(tmp_path):
    text = (
        "<skills_instructions>\n"
        "- Word Word Word: Does C: with a colon. (file: /s/c/SKILL.md)\n"
        "- Name With Spaces: (file: /s/n/SKILL.md)\n"
        "- `alias` = `/Users/x/.codex/skills`\n"
        "</skills_instructions>"
    )
    write_log(tmp_path, "a", [meta(), skills(text)], 100)
    got = last_codex_list(tmp_path, None)
    assert got.list.skills == (
        ("Word Word Word", "Does C: with a colon."),
        ("Name With Spaces", ""),
    )
    assert got.paths == {"Word Word Word": "/s/c/SKILL.md", "Name With Spaces": "/s/n/SKILL.md"}


def test_roots_lines_are_ignored(tmp_path):
    text = (
        "<skills_instructions>\n"
        "### Skill roots\n"
        "- `alias` = `/Users/x/.codex/skills`\n"
        "- `plug` = `/Users/x/.codex/plugins/cache`\n"
        "### Available skills\n"
        "- a: Does A. (file: /s/a/SKILL.md)\n"
        "</skills_instructions>"
    )
    write_log(tmp_path, "a", [meta(), skills(text)], 100)
    assert last_codex_list(tmp_path, None).list.skills == (("a", "Does A."),)


def test_a_path_under_a_root_alias_becomes_absolute(tmp_path):
    text = (
        "<skills_instructions>\n"
        "### Skill roots\n"
        "- `r2` = `/Users/x/.codex/skills`\n"
        "### Available skills\n"
        "- a: Does A. (file: r2/a/SKILL.md)\n"
        "- b: (file: /s/b/SKILL.md)\n"
        "- c: Does C. (file: r9/c/SKILL.md)\n"
        "</skills_instructions>"
    )
    write_log(tmp_path, "a", [meta(), skills(text)], 100)
    assert last_codex_list(tmp_path, None).paths == {
        "a": "/Users/x/.codex/skills/a/SKILL.md",  # the alias is resolved
        "b": "/s/b/SKILL.md",  # an absolute path stays
        "c": "r9/c/SKILL.md",  # an unknown alias is left as it is
    }
    got = last_codex_list(tmp_path, None)
    assert got.shown["a"] == "r2/a/SKILL.md"  # as the line shows it, for Codex's own count
    assert got.roots == ("- `r2` = `/Users/x/.codex/skills`",)


def test_a_mixed_block_parses_every_skill_line(tmp_path):
    skill_lines = [
        "- a: Does A. (file: /s/a/SKILL.md)",
        "- b: (file: /s/b/SKILL.md)",
        "- superpowers:brainstorming: Use when: creating things. (file: /p/br/SKILL.md)",
        "- superpowers:debug: (file: /p/d/SKILL.md)",
    ]
    roots = ["- `alias` = `/Users/x/.codex/skills`", "- `p` = `/Users/x/plugins`"]
    lines = [roots[0], skill_lines[0], skill_lines[1], roots[1], *skill_lines[2:], "Use them well."]
    text = "<skills_instructions>\n" + "\n".join(lines) + "\n</skills_instructions>"
    write_log(tmp_path, "a", [meta(), skills(text)], 100)
    got = last_codex_list(tmp_path, None)
    assert len(got.list.skills) == len(skill_lines)
    assert [name for name, _ in got.list.skills] == [
        "a",
        "b",
        "superpowers:brainstorming",
        "superpowers:debug",
    ]
    assert got.list.skills[2] == ("superpowers:brainstorming", "Use when: creating things.")


def test_skips_threads_not_started_by_a_person_and_zst_files(tmp_path):
    write_log(tmp_path, "person", [meta(), skills(LIST.replace("Does A.", "Mine."))], 100)
    write_log(tmp_path, "sub", [meta(source="subagent"), skills()], 200)
    zst = tmp_path / "sessions/2026/11/08/rollout-old.jsonl.zst"
    zst.write_bytes(b"\x28\xb5\x2f\xfd not json")
    os.utime(zst, (300, 300))
    assert last_codex_list(tmp_path, None).list.skills[0] == ("a", "Mine.")


def test_the_date_is_the_list_entry_not_the_file(tmp_path):
    write_log(tmp_path, "a", [meta(), skills(at="2026-11-01T09:00:00Z")], time.time())
    assert last_codex_list(tmp_path, None).list.at == "2026-11-01T09:00:00Z"


def stamp(at: str) -> float:
    return datetime.fromisoformat(at).timestamp()


def test_the_newest_list_wins_not_the_newest_file(tmp_path):
    # Codex rewrites an old chat's file when the app opens it, with no new list.
    old = skills(LIST.replace("Does A.", "Old."), at="2026-10-26T19:00:00Z")
    write_log(tmp_path, "old", [meta(), old], stamp("2026-11-12T17:10:00Z"))
    write_log(
        tmp_path, "new", [meta(), skills(at="2026-11-11T23:00:00Z")], stamp("2026-11-11T23:05:00Z")
    )
    got = last_codex_list(tmp_path, None).list
    assert (got.at, got.skills[0]) == ("2026-11-11T23:00:00Z", ("a", "Does A."))


def test_a_newer_unreadable_list_wins_over_an_older_good_one(tmp_path):
    odd = skills(
        "<skills_instructions>\n- a | Does A.\n</skills_instructions>", at="2026-11-11T09:00:00Z"
    )
    write_log(
        tmp_path, "good", [meta(), skills(at="2026-11-10T09:00:00Z")], stamp("2026-11-12T09:00:00Z")
    )
    write_log(tmp_path, "odd", [meta(), odd], stamp("2026-11-11T09:05:00Z"))
    assert isinstance(last_codex_list(tmp_path, None), Unreadable)


def test_the_last_list_in_a_thread_wins(tmp_path):
    old = LIST.replace("Does A.", "Old.")
    entries = [meta(), turn("m1"), skills(old), turn("m2"), skills()]
    write_log(tmp_path, "a", entries, 100)
    got = last_codex_list(tmp_path, None).list
    assert got.skills[0] == ("a", "Does A.")
    assert got.model == "m2"


def test_only_a_developer_message_counts(tmp_path):
    write_log(tmp_path, "a", [meta(), skills(role="user")], 100)
    assert last_codex_list(tmp_path, None) is None


def test_a_picked_folder_reads_only_its_own_logs(tmp_path):
    write_log(tmp_path, "mine", [meta("/work/a"), skills(LIST.replace("Does A.", "Mine."))], 100)
    write_log(tmp_path, "other", [meta("/work/b"), skills(LIST.replace("Does A.", "Other."))], 200)
    assert last_codex_list(tmp_path, "/work/a").list.skills[0] == ("a", "Mine.")
    assert last_codex_list(tmp_path, None).list.skills[0] == ("a", "Other.")
    assert last_codex_list(tmp_path, "/work/none") is None


def test_no_logs_at_all_is_none(tmp_path):
    assert last_codex_list(tmp_path, None) is None


def test_a_log_with_no_list_yet_falls_back_to_the_next_older(tmp_path):
    write_log(tmp_path, "old", [meta(), skills(LIST.replace("Does A.", "Old."))], 100)
    write_log(tmp_path, "new", [meta(), turn()], 200)
    assert last_codex_list(tmp_path, None).list.skills[0] == ("a", "Old.")


def test_a_half_written_last_line_is_skipped(tmp_path):
    tail = '{"type": "response_item", "payload": {"content": [{"text": "<skills_instructions>\\n- a'
    write_log(tmp_path, "a", [meta(), skills()], 100, raw_tail=tail)
    assert last_codex_list(tmp_path, None).list.skills[0] == ("a", "Does A.")


def test_a_list_with_unknown_lines_is_unreadable_on_any_version(tmp_path):
    for version in ("0.150.0", "0.163.0-alpha.11", "9.9.9"):
        write_log(tmp_path, "old", [meta(), skills()], 100)
        odd = "<skills_instructions>\n- a | Does A. | /s/a/SKILL.md\n</skills_instructions>"
        write_log(tmp_path, "new", [meta(version=version), skills(odd)], 200)
        assert last_codex_list(tmp_path, None) == Unreadable("codex", version)


def test_a_list_block_with_no_skill_lines_is_no_list(tmp_path):
    write_log(tmp_path, "old", [meta(), skills()], 100)
    empty = "<skills_instructions>\nUse a skill when it fits.\n</skills_instructions>"
    write_log(tmp_path, "new", [meta(), skills(empty)], 200)
    assert last_codex_list(tmp_path, None).list.skills[0] == ("a", "Does A.")


def test_a_good_list_after_an_odd_one_is_read(tmp_path):
    odd = "<skills_instructions>\n- a | Does A.\n</skills_instructions>"
    write_log(tmp_path, "a", [meta(), skills(odd), skills()], 100)
    assert last_codex_list(tmp_path, None).list.skills[0] == ("a", "Does A.")


def test_a_log_with_no_list_falls_back_whatever_its_version(tmp_path):
    for version in ("0.150.0", "9.9.9"):
        write_log(tmp_path, "old", [meta(), skills()], 100)
        write_log(tmp_path, "new", [meta(version=version), turn()], 200)
        assert last_codex_list(tmp_path, None).list.skills[0] == ("a", "Does A.")


def test_another_version_with_a_readable_list_is_read(tmp_path):
    write_log(tmp_path, "new", [meta(version="0.164.0"), skills()], 100)
    assert last_codex_list(tmp_path, None).list.version == "0.164.0"


def test_a_newer_log_that_is_not_a_person_log_or_folder_is_skipped(tmp_path):
    write_log(tmp_path, "old", [meta(), skills()], 100)
    write_log(tmp_path, "sub", [meta(version="0.164.0", source="subagent")], 200)
    write_log(tmp_path, "elsewhere", [meta("/work/b", version="0.164.0")], 300)
    assert last_codex_list(tmp_path, "/work/a").list.skills[0] == ("a", "Does A.")


def test_a_file_that_cannot_be_read_is_skipped(tmp_path):
    write_log(tmp_path, "ok", [meta(), skills()], 100)
    (tmp_path / "sessions/2026/11/08/rollout-dir.jsonl").mkdir()  # opening it fails
    (tmp_path / "sessions/2026/11/08/rollout-gone.jsonl").symlink_to(tmp_path / "missing")
    assert last_codex_list(tmp_path, None).list.skills[0] == ("a", "Does A.")


def test_only_the_lines_that_can_matter_are_parsed(tmp_path):
    path = tmp_path / "sessions/2026/11/08/rollout-big.jsonl"
    path.parent.mkdir(parents=True)
    other = json.dumps({"type": "response_item", "payload": {"text": "x" * 200}})
    big = json.dumps({"type": "response_item", "payload": {"text": "y" * 20_000}})
    lines = [json.dumps(meta()), json.dumps(turn())] + [other] * 50_000 + [big] * 2_000
    lines.insert(25_000, json.dumps(skills()))
    path.write_text("\n".join(lines) + "\n")
    start = time.perf_counter()
    got = last_codex_list(tmp_path, None)
    assert time.perf_counter() - start < 1
    assert got.list.skills == (("a", "Does A."), ("b", ""))
    assert got.list.model == "gpt-6-astra"


def cache(home: Path, models):
    (home / "models_cache.json").write_text(json.dumps({"models": models}))


def test_window_comes_from_the_model_cache(tmp_path):
    cache(
        tmp_path, [{"slug": "gpt-6-astra", "display_name": "GPT-6-Astra", "context_window": 272000}]
    )
    assert codex_window(tmp_path, "gpt-6-astra") == 272000
    assert codex_window(tmp_path, "other") is None
    assert codex_window(tmp_path, None) is None


def test_no_or_broken_model_cache_is_no_window(tmp_path):
    assert codex_window(tmp_path, "gpt-6-astra") is None
    assert codex_windows(tmp_path) == []
    (tmp_path / "models_cache.json").write_text("{not json")
    assert codex_window(tmp_path, "gpt-6-astra") is None
    assert codex_windows(tmp_path) == []
    cache(tmp_path, [{"slug": "m"}, "odd", {"slug": "n", "context_window": "big"}])
    assert codex_window(tmp_path, "m") is None
    assert codex_window(tmp_path, "n") is None
    assert codex_windows(tmp_path) == []


def test_windows_group_display_names_by_size(tmp_path):
    cache(
        tmp_path,
        [
            {"slug": "a", "display_name": "GPT-6-Astra", "context_window": 272000},
            {"slug": "b", "display_name": "GPT-6-Mini", "context_window": 128000},
            {"slug": "c", "display_name": "GPT-6", "context_window": 272000},
            {"slug": "d", "context_window": 272000},
        ],
    )
    assert codex_windows(tmp_path) == [(128000, ["GPT-6-Mini"]), (272000, ["GPT-6-Astra", "GPT-6"])]


def test_a_model_cache_with_no_model_list_is_no_window(tmp_path):
    (tmp_path / "models_cache.json").write_text('{"models": null}')
    assert codex_window(tmp_path, "m") is None
    (tmp_path / "models_cache.json").write_text("[]")
    assert codex_windows(tmp_path) == []


ASTRA = {"slug": "gpt-6-astra", "display_name": "GPT-6-Astra", "context_window": 272000}


def test_the_window_set_in_config_is_used_up_to_the_models_most(tmp_path):
    # Codex's own rule: model_context_window replaces the window, but not above
    # max_context_window (codex-rs models-manager, checked 2026-11-12).
    cache(tmp_path, [ASTRA | {"max_context_window": 872000}, {"slug": "m", "context_window": 8}])
    (tmp_path / "config.toml").write_text("model_context_window = 1000000\n")
    assert codex_window(tmp_path, "gpt-6-astra") == 872000
    assert codex_window(tmp_path, "m") == 1000000  # no most: the setting as it is
    assert codex_windows(tmp_path) == [(872000, ["GPT-6-Astra"]), (1000000, [])]
    (tmp_path / "config.toml").write_text("model_context_window = 128000\n")
    assert codex_window(tmp_path, "gpt-6-astra") == 128000


def test_a_window_setting_that_is_not_a_whole_number_is_ignored(tmp_path):
    cache(tmp_path, [ASTRA | {"max_context_window": 872000}])
    for text in ('model_context_window = "big"\n', "model_context_window = 0\n", "not toml ["):
        (tmp_path / "config.toml").write_text(text)
        assert codex_window(tmp_path, "gpt-6-astra") == 272000
