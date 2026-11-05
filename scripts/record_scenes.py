"""The README's pictures, played on the real page with Playwright: two stills and two short
animations (one of them, `pick`, is for posts).

Used by scripts/record_readme.py, which starts a fresh page for each one. An animated scene is
set up first, then filmed: the page runs on a paused clock that moves one frame at a time, and
the part of the page the scene is about is saved after each step. So the motion is as even as
on a real screen, however long a frame takes to save. img2webp joins the frames into one looping
WebP. A drawn cursor shows the pointer, since a headless browser shows none.
"""

import math
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

VIEW = {"width": 1280, "height": 800}
SCALE = 1.5  # device pixels per CSS pixel; the README shows each animation at its CSS size
FPS = 30

# A pointer drawn on the page: it follows the mouse and dips at its tip while pressed.
# Animations note when they start in page time, so a filmed frame can show each one where it
# should be.
CURSOR = """
(() => {
  const animate = Element.prototype.animate;
  Element.prototype.animate = function (...args) {
    const motion = animate.apply(this, args);
    motion.filmStart = performance.now();
    return motion;
  };
  const arrow = '<svg width="22" height="22" viewBox="0 0 16 16">'
    + '<path d="M2 1 L14 8 L8.6 9.4 L6.1 15 Z" fill="#fff" stroke="#161a21"'
    + ' stroke-width="1.1" stroke-linejoin="round"/></svg>';
  const draw = () => {
    if (document.getElementById('readme-cursor')) return;
    const c = document.createElement('div');
    c.id = 'readme-cursor';
    c.innerHTML = arrow;
    Object.assign(c.style, {
      position: 'fixed', left: '0', top: '0', width: '22px', height: '22px',
      transformOrigin: '3px 2px', zIndex: 2147483647, pointerEvents: 'none',
      translate: '-100px -100px', transition: 'scale 120ms ease',
      filter: 'drop-shadow(0 1px 2px rgba(0,0,0,.35))',
    });
    document.documentElement.append(c);
    // `translate`, not `transform`: the press scale then shrinks it at its tip, not toward 0,0.
    const at = (e) => { c.style.translate = `${e.clientX - 3}px ${e.clientY - 2}px`; };
    addEventListener('pointermove', at, true);
    addEventListener('pointerdown', () => { c.style.scale = '0.86'; }, true);
    addEventListener('pointerup', () => { c.style.scale = '1'; }, true);
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', draw);
  else draw();
})();
"""

# Puts every running animation at the page's time. One found here for the first time (a CSS
# transition) started after the last frame.
SYNC = """
() => {
  const now = performance.now();
  const before = window.filmAt ?? now;
  window.filmAt = now;
  for (const motion of document.getAnimations()) {
    if (motion.filmStart === undefined) motion.filmStart = before;
    if (motion.playState === 'finished' || !motion.effect) continue;
    const at = now - motion.filmStart;
    if (at >= motion.effect.getComputedTiming().endTime) motion.finish();
    else { motion.pause(); motion.currentTime = at; }
  }
}
"""


class Film:
    """The page on a paused clock: each step moves it one frame on and saves that frame."""

    def __init__(self, page: Page, clip: dict, folder: Path):
        self.page, self.clip, self.folder = page, clip, folder
        self.frames = 0
        self.ms = 0.0  # page time since filming started
        self.done = 0  # whole ms the clock has run

    def start(self) -> None:
        self.page.clock.pause_at(self.page.evaluate("Date.now()") + 50)

    def step(self, keep: bool = True) -> None:
        self.ms += 1000 / FPS
        self.page.clock.run_for(round(self.ms) - self.done)
        self.done = round(self.ms)
        self.page.evaluate(SYNC)
        if keep:
            path = self.folder / f"{self.frames:05d}.png"
            self.page.screenshot(path=path, clip=self.clip)
            self.frames += 1

    def hold(self, seconds: float) -> None:
        for _ in range(round(seconds * FPS)):
            self.step()

    def freeze(self, seconds: float) -> None:
        """Keep the last frame on screen while page time stands still."""
        last = self.folder / f"{self.frames - 1:05d}.png"
        for _ in range(round(seconds * FPS)):
            shutil.copy(last, self.folder / f"{self.frames:05d}.png")
            self.frames += 1

    def still(self) -> None:
        """One picture instead of frames: the scene is a still."""
        self.page.screenshot(path=self.folder / "still.png", clip=self.clip)

    def loop(self, seconds: float = 0.4) -> None:
        """Fade the last frame into the first, so the loop starts again without a jump."""
        last = self.folder / f"{self.frames - 1:05d}.png"
        first = self.folder / "00000.png"
        steps = round(seconds * FPS)
        for i in range(1, steps + 1):
            share = ease(i / (steps + 1))
            path = self.folder / f"{self.frames:05d}.png"
            run_ffmpeg(
                "-i",
                str(last),
                "-i",
                str(first),
                "-filter_complex",
                f"[1][0]blend=all_mode=normal:all_opacity={share:.3f}",
                str(path),
            )
            self.frames += 1

    def until(self, selector: str, seconds: float = 20, gone: bool = False) -> None:
        """Let page time pass without filming until the selector shows (or is `gone`): waiting
        is cut out."""
        node = self.page.locator(selector).first
        end = time.monotonic() + seconds
        while node.is_visible() == gone:
            if time.monotonic() > end:
                raise TimeoutError(selector)
            self.step(keep=False)


def ease(t: float) -> float:
    return 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


class Pointer:
    """Moves the mouse along an eased, slightly curved path, as a hand would."""

    def __init__(self, page: Page, film: Film, x: float = 640, y: float = 700):
        self.page, self.film, self.x, self.y = page, film, x, y
        page.mouse.move(x, y)

    def jump(self, x: float, y: float) -> None:
        """Before filming: put the pointer there at once."""
        self.page.mouse.move(x, y)
        self.x, self.y = x, y

    def glide(self, x: float, y: float, seconds: float = 0.7) -> None:
        x0, y0 = self.x, self.y
        bow = 0.08 * math.hypot(x - x0, y - y0)  # a hand's path bends a little
        nx, ny = (y0 - y, x - x0) if (x, y) != (x0, y0) else (0, 0)
        size = math.hypot(nx, ny) or 1
        steps = max(1, round(seconds * FPS))
        for i in range(1, steps + 1):
            t = ease(i / steps)
            side = bow * math.sin(math.pi * t) / size
            self.page.mouse.move(x0 + (x - x0) * t + nx * side, y0 + (y - y0) * t + ny * side)
            self.film.step()
        self.x, self.y = x, y

    def to(self, selector: str, seconds: float = 0.7, dx: float = 0.5, dy: float = 0.5) -> None:
        box = self.page.locator(selector).first.bounding_box()
        self.glide(box["x"] + box["width"] * dx, box["y"] + box["height"] * dy, seconds)

    def click(self, selector: str, seconds: float = 0.7) -> None:
        self.to(selector, seconds)
        self.film.hold(0.12)
        self.page.mouse.down()
        self.film.hold(0.08)
        self.page.mouse.up()

    def drag(self, x: float, y: float, seconds: float = 1.0) -> None:
        """Press, drag to (x, y) and keep holding there."""
        self.page.mouse.down()
        self.film.hold(0.12)
        self.glide(self.x + 8, self.y + 6, 0.12)  # past the drag threshold
        self.glide(x, y, seconds)


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


def scene_pick(page: Page, film: Film, pointer: Pointer) -> None:
    """Three servers are picked with a band and dragged onto the gateway together."""
    first = page.locator('[data-focus="block:outside:move:context7"]').bounding_box()
    last = page.locator('[data-focus="block:outside:local:playwright"]').bounding_box()
    # From just above context7, the first outside, so the band takes all three.
    pointer.jump(first["x"] + first["width"] + 26, first["y"] - 3)
    film.start()
    film.hold(0.5)
    page.mouse.down()
    pointer.glide(first["x"] - 18, last["y"] + last["height"] + 12, 0.9)
    page.mouse.up()
    film.hold(0.4)
    pointer.glide(first["x"] + 40, first["y"] + first["height"] / 2, 0.6)
    film.hold(0.15)
    pointer.drag(*low_on_gateway(page), 1.1)
    film.hold(1.6)  # held over the lit gateway
    film.loop()


def link_point(page: Page, tool: str, share: float = 0.75) -> tuple[float, float]:
    """A point on the map's link from memory to one of its tools, `share` of the way along."""
    return page.locator(f'[data-focus="link:held:kitden:memory>tool:memory/{tool}"]').evaluate(
        """(path, share) => {
          const at = path.getPointAtLength(path.getTotalLength() * share);
          const p = new DOMPoint(at.x, at.y).matrixTransform(path.getScreenCTM());
          return [p.x, p.y];
        }""",
        share,
    )


def scene_tools(page: Page, film: Film, pointer: Pointer) -> None:
    """memory is in the gateway with its tools. The three that delete are turned off on the map
    and applied for every agent."""
    memory = page.locator('[data-focus="block:outside:local:memory"]').bounding_box()
    page.mouse.move(memory["x"] + 40, memory["y"] + memory["height"] / 2)
    page.mouse.down()
    page.mouse.move(*center(page, '[data-focus="block:gateway:kitden"]'), steps=12)
    page.mouse.up()
    page.locator("#dock button:has-text('Apply')").first.click()
    held = page.locator('[data-focus="block:held:kitden:memory"]')
    held.wait_for()
    held.click()
    page.locator("#drawer button:has-text('Close')").first.click()
    time.sleep(0.5)
    pointer.jump(*link_point(page, "read_graph", 0.6))
    film.start()
    film.until("text=Moved memory into", 60, gone=True)  # its note leaves in 9 s
    film.hold(0.3)
    for tool in ("delete_entities", "delete_observations", "delete_relations"):
        pointer.glide(*link_point(page, tool), 0.55)
        film.hold(0.3)  # the link lights and shows its ×
        pointer.click(f"[aria-label='Turn off {tool}']", 0.35)
        film.hold(0.35)
    film.hold(0.3)
    pointer.click("#dock button:has-text('Apply')", 0.6)
    film.hold(1.6)
    film.loop()


def open_library(page: Page, link: str) -> None:
    page.goto(link)
    page.goto(link.split("/?")[0] + "/#library")
    page.locator('[data-focus="block:client:codex"]').wait_for()
    time.sleep(1.2)  # the map has landed


def scene_library(page: Page, film: Film, pointer: Pointer) -> None:
    """One still picture: the Library map, which agent loads which plugin and skill. The pointer
    stays out of it."""
    pointer.jump(1100, 700)
    time.sleep(0.4)
    film.still()


def open_find(page: Page, link: str) -> None:
    open_library(page, link)
    page.locator("button:has-text('Add plugins')").first.click()
    page.locator("[aria-label='Search catalogs']").wait_for()
    page.locator(".discovery-results .res").first.wait_for()


def scene_find(page: Page, film: Film, pointer: Pointer) -> None:
    """One still picture: a search of the catalogs, one result's details, and the agents it is
    added to."""
    search = page.locator("[aria-label='Search catalogs']")
    search.fill("mcp")
    search.press("Enter")
    page.locator(".discovery-results .res:has-text('mcp-builder')").click()
    inspector = page.locator(".discovery-inspector")
    inspector.locator("text=Add to").wait_for()
    for client in ("Claude Code", "Codex"):
        inspector.locator(f"label:has-text('{client}')").click()
    pointer.jump(60, 700)
    time.sleep(0.6)
    film.still()


# A scene that needs a taller window than VIEW, so its panel shows whole.
VIEWS = {"find": {"width": 1280, "height": 1000}}
OPEN = {"library": open_library, "find": open_find}

# The part of the page each animation shows, in CSS pixels: x, y, width, height.
SCENES = (
    ("library", scene_library, (180, 255, 470, 370)),  # the clients and their plugins, a still
    ("find", scene_find, (661, 110, 580, 850)),  # the add panel after a search, a still
    ("pick", scene_pick, (355, 318, 450, 300)),  # the gateway and the servers outside it
    ("tools", scene_tools, (180, 235, 860, 500)),  # memory, its tools and the changes waiting
)


def run_ffmpeg(*args: str) -> None:
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    # Fixed arguments; ffmpeg from PATH is the point.
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", *args], check=True)  # noqa: S603


def encode(frames: Path, out: Path) -> None:
    """One looping WebP from the numbered frames. Lossy WebP leaves dark blocks where frames
    differ a little, so it is near-lossless: no colour moves more than a few steps."""
    args = ["-loop", "0", "-lossless", "-near_lossless", "60", "-m", "6"]
    for index, frame in enumerate(sorted(frames.glob("*.png"))):
        ms = round((index + 1) * 1000 / FPS) - round(index * 1000 / FPS)
        args += ["-d", str(ms), str(frame)]
    img2webp = shutil.which("img2webp") or "img2webp"
    # Fixed arguments; img2webp from PATH is the point.
    subprocess.run([img2webp, *args, "-o", str(out)], check=True, capture_output=True)  # noqa: S603


def record_all(fresh_page, out: Path, only: str = "") -> None:
    """Make every scene's animation in light and dark, each on a fresh page; `only` keeps the
    ones whose name (as "pick-dark") starts with it."""
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
                    viewport=VIEWS.get(name, VIEW), device_scale_factor=SCALE, color_scheme=theme
                )
                context.add_init_script(CURSOR)
                page = context.new_page()
                page.clock.install()
                clip = {"x": x, "y": y, "width": w, "height": h}
                with tempfile.TemporaryDirectory() as frames:
                    try:
                        OPEN.get(name, open_gateway)(page, link)
                        film = Film(page, clip, Path(frames))
                        play(page, film, Pointer(page, film))
                    finally:
                        context.close()
                        server.should_exit = True
                    still = Path(frames) / "still.png"
                    if still.exists():
                        target = out / f"{name}-{theme}.png"
                        shutil.copy(still, target)
                        length = "a still"
                    else:
                        target = out / f"{name}-{theme}.webp"
                        encode(Path(frames), target)
                        length = f"{film.frames / FPS:.1f} s"
                print(f"{target.name}: {length}, {target.stat().st_size // 1024} KB")
        browser.close()
