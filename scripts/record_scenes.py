"""The README's three pictures, played on the real page with Playwright.

Used by scripts/record_readme.py, which starts a fresh page for each picture. Each scene is
played up to its key moment, and the part of the page it is about is saved as a PNG. A drawn
cursor shows the pointer, since a headless browser shows none.
"""

import time
from functools import partial
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

VIEW = {"width": 1280, "height": 800}
SCALE = 2  # device pixels per CSS pixel, so text stays sharp

# A pointer drawn on the page: it follows the mouse and dips while pressed.
CURSOR = """
(() => {
  const arrow = '<svg width="22" height="22" viewBox="0 0 16 16">'
    + '<path d="M2 1 L14 8 L8.6 9.4 L6.1 15 Z" fill="#fff" stroke="#161a21"'
    + ' stroke-width="1.1" stroke-linejoin="round"/></svg>';
  const draw = () => {
    if (document.getElementById('readme-cursor')) return;
    const c = document.createElement('div');
    c.id = 'readme-cursor';
    c.innerHTML = arrow;
    Object.assign(c.style, {
      position: 'fixed', left: '0', top: '0', zIndex: 2147483647, pointerEvents: 'none',
      transform: 'translate(-100px,-100px)', transition: 'scale 120ms ease',
      filter: 'drop-shadow(0 1px 2px rgba(0,0,0,.35))',
    });
    document.documentElement.append(c);
    const at = (e) => { c.style.transform = `translate(${e.clientX - 3}px, ${e.clientY - 2}px)`; };
    addEventListener('pointermove', at, true);
    addEventListener('pointerdown', () => { c.style.scale = '0.86'; }, true);
    addEventListener('pointerup', () => { c.style.scale = '1'; }, true);
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', draw);
  else draw();
})();
"""


class Pointer:
    """Moves the mouse along an eased path, as a hand would, so the page sees every step."""

    def __init__(self, page: Page, x: float = 640, y: float = 700):
        self.page, self.x, self.y = page, x, y
        page.mouse.move(x, y)

    def glide(self, x: float, y: float, seconds: float = 0.7) -> None:
        steps = max(2, int(seconds * 60))
        x0, y0 = self.x, self.y
        for i in range(1, steps + 1):
            t = i / steps
            ease = 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2
            self.page.mouse.move(x0 + (x - x0) * ease, y0 + (y - y0) * ease)
            time.sleep(seconds / steps)
        self.x, self.y = x, y

    def to(self, selector: str, seconds: float = 0.7, dx: float = 0.5, dy: float = 0.5) -> None:
        box = self.page.locator(selector).first.bounding_box()
        self.glide(box["x"] + box["width"] * dx, box["y"] + box["height"] * dy, seconds)

    def click(self, selector: str, seconds: float = 0.7) -> None:
        self.to(selector, seconds)
        time.sleep(0.12)
        self.page.mouse.down()
        time.sleep(0.09)
        self.page.mouse.up()

    def drag(self, x: float, y: float, seconds: float = 1.0, over=None) -> None:
        """Drag to (x, y) and let go; `over` runs while the pointer is still held there."""
        self.page.mouse.down()
        time.sleep(0.15)
        self.glide(self.x + 8, self.y + 6, 0.15)  # past the drag threshold
        self.glide(x, y, seconds)
        time.sleep(0.25)
        if over:
            over()
        self.page.mouse.up()


def center(page: Page, selector: str) -> tuple[float, float]:
    box = page.locator(selector).first.bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def low_on_gateway(page: Page) -> tuple[float, float]:
    """A point low on the gateway: what is held there does not hide its name while it lights."""
    box = page.locator('[data-focus="block:gateway:kitden"]').bounding_box()
    return box["x"] + box["width"] * 0.4, box["y"] + box["height"] - 10


def open_gateway(page: Page, link: str) -> None:
    page.goto(link)
    page.goto(link.split("/?")[0] + "/#gateway")
    page.locator('[data-focus="block:gateway:kitden"]').wait_for()
    time.sleep(1.2)  # the map has landed


def scene_find(page: Page, pointer: Pointer, moment) -> None:
    """Search the MCP Registry for Context7 and drag it onto the gateway. The moment: Context7
    held over the lit gateway."""
    time.sleep(0.6)
    pointer.click("button:has-text('+ Add servers')", 0.9)
    page.locator("#drawer .res").first.wait_for(timeout=20000)
    time.sleep(0.8)
    pointer.click("#drawer input[type=search]", 0.6)
    page.keyboard.type("context7", delay=120)
    page.keyboard.press("Enter")
    row = page.locator("#drawer .res.drags", has_text="upstash").first
    row.wait_for(timeout=20000)
    time.sleep(1.0)
    box = row.bounding_box()
    pointer.glide(box["x"] + 40, box["y"] + box["height"] / 2, 0.8)
    time.sleep(0.2)
    pointer.drag(*low_on_gateway(page), 1.3, over=moment)


def scene_pick(page: Page, pointer: Pointer, moment) -> None:
    """Band-pick the three local servers and drag them onto the gateway together. The moment: the
    three held over the lit gateway."""
    first = page.locator('[data-focus="block:outside:local:memory"]').bounding_box()
    last = page.locator('[data-focus="block:outside:local:sequential-thinking"]').bounding_box()
    time.sleep(0.6)
    # From just above memory, below stripe, so the band takes only the local servers.
    pointer.glide(first["x"] + first["width"] + 26, first["y"] - 3, 0.8)
    page.mouse.down()
    pointer.glide(first["x"] - 18, last["y"] + last["height"] + 12, 1.1)
    page.mouse.up()
    time.sleep(0.7)
    pointer.glide(first["x"] + 40, first["y"] + first["height"] / 2, 0.7)
    time.sleep(0.2)
    pointer.drag(*low_on_gateway(page), 1.2, over=moment)


def scene_token(page: Page, pointer: Pointer, moment) -> None:
    """Drag Stripe in: it waits for a token; type it. The moment: the token works and the change
    waits for Apply."""
    time.sleep(0.6)
    pointer.to('[data-focus="block:outside:move:stripe"]', 0.8, dx=0.25)
    time.sleep(0.2)
    pointer.drag(*center(page, '[data-focus="block:gateway:kitden"]'), 1.2)
    page.locator("#dock button:has-text('Add token')").wait_for(timeout=20000)
    time.sleep(1.2)
    pointer.click("#dock button:has-text('Add token')", 0.8)
    field = page.locator("#drawer input[type=password]").first
    field.wait_for()
    time.sleep(0.5)
    pointer.click("#drawer input[type=password]", 0.5)
    page.keyboard.type("sk_test_51ReadmeSampleKey", delay=45)
    time.sleep(0.3)
    pointer.click("#drawer button:has-text('Add token')", 0.6)
    page.locator("#drawer .access-works").wait_for(state="visible", timeout=20000)
    page.evaluate("scrollTo(0, 0)")  # typing scrolled the page a little
    time.sleep(0.15)  # before the panel closes on its own
    moment()


# The part of the page each picture shows, in CSS pixels: x, y, width, height.
SCENES = (
    ("find", scene_find, (360, 240, 885, 372)),  # the gateway and the catalog's results
    ("pick", scene_pick, (355, 318, 450, 300)),  # the gateway and the servers outside it
    ("token", scene_token, (360, 240, 885, 300)),  # the gateway, Stripe and the token panel
)


def record_all(fresh_page, out: Path, only: str = "") -> None:
    """Save every scene's picture in light and dark, each on a fresh page; `only` keeps the
    pictures whose name (as "pick-dark") starts with it."""
    out.mkdir(parents=True, exist_ok=True)
    run = 0
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for name, play, (x, y, w, h) in SCENES:
            for theme in ("light", "dark"):
                if not f"{name}-{theme}".startswith(only):
                    continue
                link, server = fresh_page(run)
                run += 1
                context = browser.new_context(
                    viewport=VIEW, device_scale_factor=SCALE, color_scheme=theme
                )
                context.add_init_script(CURSOR)
                page = context.new_page()
                target = out / f"{name}-{theme}.png"
                clip = {"x": x, "y": y, "width": w, "height": h}
                try:
                    open_gateway(page, link)
                    play(page, Pointer(page), partial(page.screenshot, path=target, clip=clip))
                    print(f"{target.name}: {target.stat().st_size // 1024} KB", flush=True)
                finally:
                    context.close()
                    server.should_exit = True
        browser.close()
