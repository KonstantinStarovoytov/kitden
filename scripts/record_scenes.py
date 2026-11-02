"""The README's three scenes, played on the real page with Playwright and saved as animated WebP.

Used by scripts/record_readme.py, which starts a fresh page for each recording. Frames come
from Chromium's screencast; a drawn cursor follows the pointer, since a headless browser shows
none. ffmpeg turns the frames into one looping WebP per scene and theme.
"""

import base64
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

VIEW = {"width": 1280, "height": 800}
SCALE = 2  # device pixels per CSS pixel, so text stays sharp
FPS = 25
WIDTH = 1600  # the WebP's width; the README shows it at up to 880 px
HOLD = 2.2  # seconds the result stays before the loop starts again

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

    def drag(self, x: float, y: float, seconds: float = 1.0) -> None:
        self.page.mouse.down()
        time.sleep(0.15)
        self.glide(self.x + 8, self.y + 6, 0.15)  # past the drag threshold
        self.glide(x, y, seconds)
        time.sleep(0.25)
        self.page.mouse.up()


def center(page: Page, selector: str) -> tuple[float, float]:
    box = page.locator(selector).first.bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


class Screencast:
    """Chromium's screencast frames with their times, written as JPEG files."""

    def __init__(self, page: Page, folder: Path):
        self.folder, self.frames = folder, []
        self.cdp = page.context.new_cdp_session(page)
        self.cdp.on("Page.screencastFrame", self._frame)

    def _frame(self, event: dict) -> None:
        path = self.folder / f"{len(self.frames):05d}.jpg"
        path.write_bytes(base64.b64decode(event["data"]))
        self.frames.append((event["metadata"]["timestamp"], path))
        self.cdp.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})

    def start(self) -> None:
        size = {"maxWidth": VIEW["width"] * SCALE, "maxHeight": VIEW["height"] * SCALE}
        self.cdp.send(
            "Page.startScreencast", {"format": "jpeg", "quality": 92, "everyNthFrame": 1, **size}
        )

    def stop(self) -> None:
        time.sleep(HOLD)
        self.frames.append((time.time(), None))  # the last frame lasts until now
        self.cdp.send("Page.stopScreencast")


def encode(frames: list, out: Path, crop: tuple[int, int, int, int] | None) -> None:
    """One looping WebP from the timed frames, cropped to (x, y, width, height) CSS pixels."""
    listing = out.with_suffix(".txt")
    lines = []
    for (time_a, path), (time_b, _) in zip(frames, frames[1:], strict=False):
        if path is not None:
            lines += [f"file '{path}'", f"duration {max(time_b - time_a, 0.001):.4f}"]
    lines.append(f"file '{frames[-2][1]}'")
    listing.write_text("\n".join(lines) + "\n")
    filters = [f"fps={FPS}"]
    if crop:
        # As shares of the frame, whatever size the screencast gave it.
        x, y, w, h = crop
        vw, vh = VIEW["width"], VIEW["height"]
        filters.append(f"crop=iw*{w}/{vw}:ih*{h}/{vh}:iw*{x}/{vw}:ih*{y}/{vh}")
    filters.append(f"scale={WIDTH}:-2:flags=lanczos")
    subprocess.run(  # noqa: S603 - fixed arguments; ffmpeg from PATH is the point
        [
            shutil.which("ffmpeg") or "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-vf",
            ",".join(filters),
            "-c:v",
            "libwebp_anim",
            "-loop",
            "0",
            "-quality",
            "82",
            "-compression_level",
            "6",
            "-preset",
            "picture",
            str(out),
        ],
        check=True,
    )
    listing.unlink()


def open_gateway(page: Page, link: str) -> None:
    page.goto(link)
    page.goto(link.split("/?")[0] + "/#gateway")
    page.locator('[data-focus="block:gateway:kitden"]').wait_for()
    time.sleep(1.2)  # the map has landed


def apply_and_wait(page: Page, pointer: Pointer) -> None:
    """Press Apply in the dock and wait for the toast that says it is done."""
    pointer.click("#dock button:has-text('Apply')", 0.8)
    page.locator(".toast").first.wait_for(timeout=20000)
    time.sleep(0.6)


def scene_find(page: Page, pointer: Pointer) -> None:
    """Search the MCP Registry for Context7, drag it onto the gateway, Apply."""
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
    pointer.drag(*center(page, '[data-focus="block:gateway:kitden"]'), 1.3)
    time.sleep(1.0)
    apply_and_wait(page, pointer)


def scene_pick(page: Page, pointer: Pointer) -> None:
    """Band-pick the three local servers, drag them onto the gateway together, Apply."""
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
    pointer.drag(*center(page, '[data-focus="block:gateway:kitden"]'), 1.2)
    page.locator("#dock button:has-text('Apply')").wait_for(timeout=20000)
    time.sleep(1.4)
    apply_and_wait(page, pointer)


def scene_token(page: Page, pointer: Pointer) -> None:
    """Drag Stripe in: it waits for a token; type it, it works, Apply."""
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
    time.sleep(1.4)
    apply_and_wait(page, pointer)


# Each scene shows the map, the side panel and the dock, without the page's rail: x, y, width,
# height in CSS pixels.
STAGE = (160, 90, 1090, 710)
SCENES = (
    ("find", scene_find, STAGE),
    ("pick", scene_pick, STAGE),
    ("token", scene_token, STAGE),
)


def record_all(fresh_page, out: Path, only: str = "") -> None:
    """Record every scene in light and dark, each on a fresh page; `only` keeps the recordings
    whose name (as "pick-dark") starts with it."""
    out.mkdir(parents=True, exist_ok=True)
    run = 0
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for name, play, crop in SCENES:
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
                frames = Path(tempfile.mkdtemp(prefix=f"kitden-{name}-"))
                try:
                    open_gateway(page, link)
                    cast = Screencast(page, frames)
                    pointer = Pointer(page)
                    cast.start()
                    play(page, pointer)
                    cast.stop()
                    target = out / f"{name}-{theme}.webp"
                    encode(cast.frames, target, crop)
                    print(
                        f"{target.name}: {len(cast.frames)} frames, "
                        f"{target.stat().st_size // 1024} KB",
                        flush=True,
                    )
                finally:
                    context.close()
                    server.should_exit = True
                    shutil.rmtree(frames, ignore_errors=True)
        browser.close()
