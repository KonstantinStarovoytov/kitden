"""Round 3, session A: Context shows the right numbers. The medium sample, changed before the page
starts: its last Claude Code chat listed 20 skills, 4 with only a name at 1% of a 200K window."""

import json
import re
import shutil

import pytest
from playwright.sync_api import expect

from kitden.demo.sample import write_claude_chat
from tests.browser.test_limit_line import open_context

pytestmark = pytest.mark.browser

LONG = "Use it when the task needs a careful plan. " * 28


@pytest.fixture
def before_start(request):
    return getattr(request, "param", lambda home: None)


def remove_brandkit(home):
    # In the last chat with only a name; gone since, as Remove from Claude Code leaves it.
    shutil.rmtree(home / ".claude/skills/brandkit")


def own_dataviz(home):
    # Claude Code has a built-in dataviz; the user adds one of the same name after the chat.
    folder = home / ".claude/skills/dataviz"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text("---\nname: dataviz\ndescription: My own charts.\n---\n")


def large_setup(home):
    # 40 long skills more: Claude Code's built-in skills fill 7,604 of the 8,000 characters.
    for i in range(40):
        folder = home / f".claude/skills/big-{i:02}"
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(f"---\nname: big-{i:02}\ndescription: {LONG}\n---\n")
    write_claude_chat(home, "claude-sonnet-4-6")


def codex_skill_off(home):
    # A Codex skill added after the last Codex chat, then turned off.
    folder = home / ".agents/skills/later"
    folder.mkdir(parents=True)
    path = folder / "SKILL.md"
    path.write_text("---\nname: later\ndescription: Added later.\n---\n")
    config = home / ".codex/config.toml"
    old = config.read_text() if config.exists() else ""
    config.write_text(f'{old}\n[[skills.config]]\npath = "{path.resolve()}"\nenabled = false\n')


def codex_system_skill(home):
    # Codex's own skill, under ~/.codex/skills/.system, in its last chat's list.
    folder = home / ".codex/skills/.system/imagegen"
    folder.mkdir(parents=True)
    path = folder / "SKILL.md"
    path.write_text("---\nname: imagegen\ndescription: Makes images.\n---\n")
    log = next((home / ".codex/sessions").rglob("*.jsonl"))
    entries = [json.loads(line) for line in log.read_text().splitlines()]
    for entry in entries:
        for part in entry.get("payload", {}).get("content", []) or []:
            text = part.get("text", "")
            if "<skills_instructions>" in text:
                line = f"- imagegen: Makes images. (file: {path.resolve()})"
                part["text"] = text.replace(
                    "<skills_instructions>\n", f"<skills_instructions>\n{line}\n"
                )
    log.write_text("".join(json.dumps(e) + "\n" for e in entries))


def pills(page, group: str) -> list[str]:
    box = page.locator(".ctx-group").filter(has=page.locator(".ctx-gname", has_text=group))
    return box.locator(".ctx-pill").evaluate_all("(n) => n.map((p) => p.dataset.skill)")


def codex_tab(page) -> None:
    main = page.locator("main")
    main.get_by_role("group", name="Client").get_by_role("button", name="Codex").click()


@pytest.mark.parametrize("before_start", [remove_brandkit], indirect=True)
def test_a_skill_removed_since_the_chat_is_gone_from_the_count(page, demo):
    # Row 1 (03-A1, 06 claim 1): it counted, as a skill Kitden cannot place, at 1,536 characters.
    open_context(page)
    main = page.locator("main")
    expect(main).to_contain_text("Your skills changed after this list was sent.")
    expect(main).to_contain_text("3 of 19 skills would show only a name")
    expect(main.locator('.ctx-pill[data-skill="brandkit"]')).to_have_count(0)
    expect(main).not_to_contain_text("Skills Kitden cannot place")
    expect(page.locator(".ctx-fix")).to_contain_text("1.1%: all 19 skills fit")


@pytest.mark.parametrize("before_start", [own_dataviz], indirect=True)
def test_a_skill_of_yours_named_like_a_built_in_one_is_a_skill_of_its_own(page, demo):
    # Row 1 (02-R04, 06 claim 2): it took the built-in's entry and its characters.
    open_context(page)
    expect(page.locator("main")).to_contain_text("Your skills changed after this list was sent.")
    assert "dataviz" in pills(page, "Built into Claude Code")
    assert "dataviz" in pills(page, "Your skills")


@pytest.mark.parametrize("before_start", [large_setup], indirect=True)
def test_a_large_setup_gets_the_largest_share_and_the_cause_in_view(page, demo):
    # Row 2 (02-R01): no handle, no button, the cause folded away.
    handle = open_context(page)
    fix = page.locator(".ctx-fix")
    expect(fix).to_contain_text("4%: 21 of 60 skills still show only a name")
    expect(fix.get_by_role("button", name="Set to 4%")).to_be_visible()
    expect(page.locator("main")).to_contain_text(
        "Claude Code's built-in skills always keep their description: they take 7,604 of the "
        "8,000 characters."
    )
    # Row 4: each place to the right leaves no more skills with only a name than the one before.
    counts = []
    for _ in range(11):
        said = handle.get_attribute("aria-valuetext") or ""
        counts.append(int(re.search(r"(\d+) of 60", said).group(1)))
        handle.press("ArrowRight")
    assert counts == sorted(counts, reverse=True), counts


@pytest.mark.parametrize("before_start", [codex_skill_off], indirect=True)
def test_a_codex_skill_turned_off_stays_struck_through_with_its_switch(page, demo):
    # Row 3 (03-A2): it vanished from Context; a Claude Code one stays.
    page.evaluate("location.hash = '#context'")
    codex_tab(page)
    pill = page.locator('.ctx-pill.off[data-skill="later"]')
    expect(pill).to_be_visible()
    pill.click()
    details = page.get_by_role("complementary", name="Details")
    expect(details).to_contain_text("Off: your next chat does not list it.")
    expect(details.get_by_role("button", name="On", exact=True)).to_be_visible()


@pytest.mark.parametrize("before_start", [codex_system_skill], indirect=True)
def test_codex_own_skills_say_the_true_reason(page, demo):
    # Row 6 (01-B1): "Kitden did not find this skill's file", though it read it.
    page.evaluate("location.hash = '#context'")
    codex_tab(page)
    assert "imagegen" in pills(page, "Built into Codex")
    main = page.locator("main")
    expect(main).not_to_contain_text("Kitden did not find this skill's file")
    group = page.locator(".ctx-group").filter(has=page.locator(".ctx-gname", has_text="Codex"))
    group.locator(".ctx-gtoggle").click()
    page.locator('.ctx-pill[data-skill="imagegen"]').click()
    details = page.get_by_role("complementary", name="Details")
    expect(details).to_contain_text("Kitden has not checked that Codex can turn this skill off")


def test_after_apply_the_overview_card_says_a_new_chat_shows_it(page, demo):
    # Row 5 (05-P3): the card stayed and still counted as needing attention.
    card = page.locator("[data-card]").filter(has_text="Skill list in Claude Code")
    card.get_by_role("button", name="Set to 1.1%", exact=True).click()
    page.locator("#dock").get_by_role("button", name="Apply").click()
    expect(page.get_by_role("button", name="Undo")).to_be_visible()
    page.evaluate("location.hash = '#overview'")
    card = page.locator("[data-card]").filter(has_text="Skill list in Claude Code")
    expect(card).to_contain_text("The limit was changed after this chat: it is 1.1% now.")
    expect(page.locator(".ov-group[data-group=attention]")).not_to_contain_text(
        "Skill list in Claude Code"
    )


def test_a_cut_skills_details_name_the_fix_context_names(page, demo):
    # Row 7 (05-P5): Details said to set another skill to Name only; Context said Set to 1.1%.
    open_context(page)
    page.locator('.ctx-pill[data-skill="brandkit"]').click()
    details = page.get_by_role("complementary", name="Details")
    expect(details).to_contain_text("No room for its description. Set to 1.1% gives it room.")
