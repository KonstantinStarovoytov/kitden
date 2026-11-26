"""Flow 18: a stack of the map under a selection. "Your skills" of the sample holds skills of Claude
Code and of Codex, so its stack mixes them. Selecting or pointing at a client brings that client's
cards to the front of the stack, and no other card of it looks lit."""

import re

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import wait_until

pytestmark = pytest.mark.browser

# Written into the sample beside its own skills. The group sorts by name, so none of the three a
# stack shows with nothing selected is Claude Code's, and both sides of its second page mix the two.
CODEX = ["aa", "ab", "ac", "ba", "bb", "mn", "yy"]
CLAUDE = ["ad", "bc", "mm", "zz"]


@pytest.fixture
def before_start():
    from tests.unit.test_context_view import skill

    def write(home):
        for name in CODEX:
            skill(home / ".codex/skills", f"{name}-codex", "Use it in Codex.")
        for name in CLAUDE:
            skill(home / ".claude/skills", f"{name}-claude", "Use it in Claude Code.")

    return write


# A stack's cards as they look, back to front, once its fades have ended: the name, whether the card
# is dim, and the colour of its edge.
CARDS = """async (node) => {
  const fades = node.getAnimations({ subtree: true });
  await Promise.all(fades.map((run) => run.finished.catch(() => {})));
  return [...node.querySelectorAll('.stack-strip, .stack-face')].map((card) => ({
    name: card.querySelector('.stack-name, .block-name').textContent,
    dim: getComputedStyle(card).filter.includes('opacity'),
    edge: getComputedStyle(card).borderTopColor,
  }));
}"""


def stack(page, group: str, role: str = "all"):
    return page.locator(f'[data-focus="block:stack:group:{group}:{role}"]')


def client(page, name: str):
    return page.locator(f'[data-focus="block:client:{name}"]')


def cards(node) -> list[dict]:
    return node.evaluate(CARDS)


def badge(node) -> str:
    """What its badge says; "" for a stack of three or fewer with nothing lit, which has none."""
    return "".join(node.locator(".stack-pill").all_inner_texts())


def place(node) -> list[str]:
    """Where a block is on the map and how big: a selection must not change it."""
    return node.evaluate("(at) => [at.style.translate, at.style.width, at.style.height]")


def landed(node) -> None:
    """Waits until the block shows whole and keeps its place: an entrance (it waits for its turn
    unseen) or a page turn has ended."""
    expect(node).to_have_css("opacity", "1")
    last = [place(node)]

    def still() -> bool:
        node.page.wait_for_timeout(150)
        last.append(place(node))
        return last[-1] == last[-2]

    wait_until(still)


def plain(node) -> tuple:
    """How a stack is with nothing selected: no card of it is dim."""
    shown = cards(node)
    assert not any(card["dim"] for card in shown)
    assert len({card["edge"] for card in shown}) == 1
    return shown, badge(node), node.get_attribute("aria-label")


def tells(node, held: list[tuple[str, bool]]) -> None:
    """The stack of `held` (each card's name, and whether the client loads it, in order) shows three
    cards: the client's first ones in front and lit, the rest behind them and dim. Its badge counts
    all the client's."""
    mine = [name for name, own in held if own]
    other = [name for name, own in held if not own]
    expect(node).to_have_class(re.compile(r"\blit\b"))
    expect(node.locator(".stack-pill")).to_have_text(f"{len(mine)} of {len(held)}")
    front = mine[:3]
    behind = other[: 3 - len(front)]
    shown = cards(node)
    assert [card["name"] for card in shown] == behind + front
    assert [card["dim"] for card in shown] == [True] * len(behind) + [False] * len(front)
    # The accent edge is on the lit cards only.
    lit = {card["edge"] for card in shown if not card["dim"]}
    assert len(lit) == 1
    assert not lit & {card["edge"] for card in shown if card["dim"]}


def let_go(page, name: str) -> None:
    """Escape, with the pointer on empty map: a client under it would light its path again (WebKit
    hears the pointer over a client once more as the map draws)."""
    page.mouse.move(5, 5)
    page.keyboard.press("Escape")
    expect(client(page, name)).not_to_have_class(re.compile(r"\bselected\b"))


@pytest.fixture
def skills(page):
    """The Library map, and for each client every skill under "Your skills", in order: its name, and
    whether the client loads it, as the server says."""
    page.get_by_role("link", name="Library", exact=True).click()
    expect(stack(page, "skills")).to_be_visible()
    landed(stack(page, "skills"))
    answer = page.evaluate("fetch('/api/library-map').then((answer) => answer.json())")
    items = next(g for g in answer["groups"] if g["key"] == "skills")["items"]
    by = {
        name: [(item["name"], item["by"].get(name) == "on") for item in items]
        for name in ("claude_code", "codex")
    }
    # Each loads some that the other does not.
    assert {(a, b) for (_, a), (_, b) in zip(*by.values(), strict=True)} >= {
        (True, False),
        (False, True),
    }
    return by


def test_a_selected_client_lights_only_its_own_skills_on_a_stack_that_mixes_two(page, skills):
    node = stack(page, "skills")
    was, at = plain(node), place(node)
    for name in ("claude_code", "codex", "claude_code"):
        client(page, name).click()
        expect(client(page, name)).to_have_class(re.compile(r"\bselected\b"))
        tells(node, skills[name])
        assert place(node) == at
        first = next(each for each, own in skills[name] if own)
        assert f" {badge(node)} linked: {first}, " in node.get_attribute("aria-label")
    let_go(page, "claude_code")
    expect(node.locator(".stack-pill")).to_have_text(was[1])
    assert plain(node) == was


def test_pointing_at_a_client_does_the_same_until_the_pointer_leaves_it(page, skills):
    node = stack(page, "skills")
    was, at = plain(node), place(node)
    for name in ("codex", "claude_code"):
        client(page, name).hover()
        tells(node, skills[name])
        assert place(node) == at
    page.get_by_role("heading", name="Library", exact=True).hover()
    expect(node.locator(".stack-pill")).to_have_text(was[1])
    assert plain(node) == was


def test_a_selection_keeps_the_page_and_tells_the_stacks_beside_it_apart(page, skills):
    """On the second page: the stack of the cards before, the five shown, the stack after."""
    stack(page, "skills").click()
    stack(page, "skills", "after").click()
    before, after = stack(page, "skills", "before"), stack(page, "skills", "after")
    expect(before).to_be_visible()
    landed(after)
    at = [place(before), place(after)]
    for name in ("claude_code", "codex"):
        every = skills[name]
        assert len(every) > 12  # three cards or more on either side
        client(page, name).click()
        # The cards between the stacks keep their own state, and the page did not turn.
        for each, own in every[5:10]:
            card = page.locator("div.map .block.skill").filter(has_text=re.compile(f"^{each}"))
            lit = re.compile(r"\blit\b")
            (expect(card).to_have_class if own else expect(card).not_to_have_class)(lit)
        for node, held in ((before, every[:5]), (after, every[10:])):
            assert any(own for _, own in held) and not all(own for _, own in held)
            tells(node, held)
        assert [place(before), place(after)] == at


def test_a_stack_with_none_of_the_clients_cards_dims_whole_and_keeps_its_front(page, skills):
    """The sample's marketplace has plugins of Claude Code's, none of Codex's."""
    node = stack(page, "marketplace:demo-market")
    was = plain(node)
    client(page, "codex").click()
    expect(stack(page, "skills")).to_have_class(re.compile(r"\blit\b"))
    expect(node).not_to_have_class(re.compile(r"\blit\b"))
    expect(node).to_have_css("filter", "opacity(0.4) saturate(0.6)")
    assert plain(node) == was


OUTSIDE = """(nodes) => nodes.map((at) => [
  at.querySelector('.block-name').textContent, at.classList.contains('lit'),
])"""


def test_on_the_gateway_a_client_lights_only_its_own_servers_on_the_outside_stack(page):
    page.get_by_role("link", name="Gateway", exact=True).click()
    node = stack(page, "outside")
    expect(node).to_be_visible()
    landed(node)
    was, at = plain(node), place(node)
    for name in ("claude_code", "codex"):
        client(page, name).click()
        expect(client(page, name)).to_have_class(re.compile(r"\bselected\b"))
        # Each server on its own card, page by page: which ones this client's lines run to.
        node.click()
        shown = page.locator("div.map .block.outside:not(.leaving)")
        expect(shown).to_have_count(5)
        held = shown.evaluate_all(OUTSIDE)
        stack(page, "outside", "after").click()
        expect(shown).to_have_count(2)
        held += shown.evaluate_all(OUTSIDE)
        assert {own for _, own in held} == {True, False}
        page.locator('[data-focus="block:collapse:group:outside"]').click()
        page.mouse.move(0, 0)  # off the stack, which comes up under the pointer
        expect(node).to_be_visible()
        landed(node)
        tells(node, held)
        assert place(node) == at
    let_go(page, "codex")
    expect(node.locator(".stack-pill")).to_have_text(was[1])
    assert plain(node) == was
