"""The README's three short animations, played on the real page with Playwright.

Used by scripts/record_readme.py, which starts a fresh page for each one. Each scene is set up
first, then filmed: the page runs on a paused clock that moves one frame at a time, and the part
of the page the scene is about is saved after each step. So the motion is as even as on a real
screen, however long a frame takes to save. ffmpeg joins the frames into one looping WebP. A
drawn cursor shows the pointer, since a headless browser shows none.
"""

import math
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

VIEW = {"width": 1280, "height": 800}
SCALE = 2  # device pixels per CSS pixel, so text stays sharp
FPS = 30
DENSITY = 1.5  # the WebP's pixels per CSS pixel; the README shows it at its CSS size

# A pointer drawn on the page: it follows the mouse and dips while pressed. Animations note when
# they start in page time, so a filmed frame can show each one where it should be.
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

    def until(self, selector: str, seconds: float = 20) -> None:
        """Let page time pass without filming until the selector shows: waiting is cut out."""
        node = self.page.locator(selector).first
        end = time.monotonic() + seconds
        while not node.is_visible():
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


def type_text(film: Film, page: Page, text: str) -> None:
    """Types as a person does, about 20 keys a second."""
    for index, key in enumerate(text):
        page.keyboard.type(key)
        film.hold(2 / FPS if index % 2 else 1 / FPS)


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


def scene_find(page: Page, film: Film, pointer: Pointer) -> None:
    """Context7, found in the catalog, is dragged onto the gateway, which lights up to take it."""
    page.locator("button:has-text('+ Add servers')").click()
    page.locator("#drawer .res").first.wait_for(timeout=20000)
    page.locator("#drawer input[type=search]").fill("context7")
    page.keyboard.press("Enter")
    row = page.locator("#drawer .res.drags", has_text="upstash").first
    row.wait_for(timeout=20000)
    time.sleep(1.0)
    box = row.bounding_box()
    pointer.jump(box["x"] + 160, box["y"] + box["height"] + 60)
    film.start()
    film.hold(0.5)
    pointer.glide(box["x"] + 40, box["y"] + box["height"] / 2, 0.6)
    film.hold(0.15)
    pointer.drag(*low_on_gateway(page), 1.1)
    film.hold(1.6)  # held over the lit gateway
    film.loop()


def scene_pick(page: Page, film: Film, pointer: Pointer) -> None:
    """Three servers are picked with a band and dragged onto the gateway together."""
    first = page.locator('[data-focus="block:outside:local:memory"]').bounding_box()
    last = page.locator('[data-focus="block:outside:local:sequential-thinking"]').bounding_box()
    # From just above memory, below stripe, so the band takes only the local servers.
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


def scene_token(page: Page, film: Film, pointer: Pointer) -> None:
    """Stripe waits in the gateway for a token; one is typed and works for every agent."""
    stripe = page.locator('[data-focus="block:outside:move:stripe"]').bounding_box()
    page.mouse.move(stripe["x"] + stripe["width"] * 0.25, stripe["y"] + stripe["height"] / 2)
    page.mouse.down()
    page.mouse.move(*center(page, '[data-focus="block:gateway:kitden"]'), steps=12)
    page.mouse.up()
    page.locator("#dock button:has-text('Add token')").click(timeout=20000)
    field = page.locator("#drawer input[type=password]").first
    field.wait_for()
    time.sleep(1.0)
    box = field.bounding_box()
    pointer.jump(box["x"] + box["width"] * 0.7, box["y"] + box["height"] + 70)
    film.start()
    film.hold(0.4)
    pointer.click("#drawer input[type=password]", 0.5)
    type_text(film, page, "sk_test_51ReadmeSampleKey")
    film.hold(0.25)
    pointer.click("#drawer button:has-text('Add token')", 0.5)
    film.until("#drawer .access-works")
    film.hold(0.45)  # the panel closes on its own soon after
    film.freeze(1.3)
    film.loop()


# The part of the page each animation shows, in CSS pixels: x, y, width, height.
SCENES = (
    ("find", scene_find, (360, 240, 885, 372)),  # the gateway and the catalog's results
    ("pick", scene_pick, (355, 318, 450, 300)),  # the gateway and the servers outside it
    ("token", scene_token, (360, 240, 885, 300)),  # the gateway, Stripe and the token panel
)


def run_ffmpeg(*args: str) -> None:
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    # Fixed arguments; ffmpeg from PATH is the point.
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", *args], check=True)  # noqa: S603


def encode(frames: Path, out: Path, width: int) -> None:
    """One looping WebP from the numbered frames."""
    run_ffmpeg(
        "-framerate",
        str(FPS),
        "-i",
        str(frames / "%05d.png"),
        "-vf",
        f"scale={width}:-2:flags=lanczos",
        "-c:v",
        "libwebp_anim",
        "-loop",
        "0",
        "-quality",
        "80",
        "-compression_level",
        "6",
        str(out),
    )


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
                    viewport=VIEW, device_scale_factor=SCALE, color_scheme=theme
                )
                context.add_init_script(CURSOR)
                page = context.new_page()
                page.clock.install()
                target = out / f"{name}-{theme}.webp"
                clip = {"x": x, "y": y, "width": w, "height": h}
                with tempfile.TemporaryDirectory() as frames:
                    try:
                        open_gateway(page, link)
                        film = Film(page, clip, Path(frames))
                        play(page, film, Pointer(page, film))
                    finally:
                        context.close()
                        server.should_exit = True
                    encode(Path(frames), target, round(w * DENSITY))
                seconds = film.frames / FPS
                print(f"{target.name}: {seconds:.1f} s, {target.stat().st_size // 1024} KB")
        browser.close()
