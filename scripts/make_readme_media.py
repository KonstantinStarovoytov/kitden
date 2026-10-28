"""Build the README images from real demo captures.

Run with --captures FOLDER to crop fresh 1280 x 720 captures (requires Pillow),
or without arguments to rebuild from the committed crops. See docs/readme-media.md.
"""

import argparse
import base64
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/images"
FRAMES = OUT / "readme"
COLOURS = {
    "light": ("#F5F6F8", "#161A21", "#464D5B", "#A44226", "#E1E4E9"),
    "dark": ("#171A20", "#F2F3F5", "#C1C6CF", "#F09A7C", "#3B424D"),
}
CROPS = {
    "start": (178, 278, 788, 663),
    "preview": (178, 278, 788, 663),
    "review": (920, 215, 1245, 610),
    "applied": (178, 278, 788, 663),
    "library": (180, 295, 1110, 480),
    "history": (185, 225, 910, 290),
    "undone": (185, 225, 910, 290),
}


def crop_captures(folder: Path) -> None:
    from PIL import Image

    FRAMES.mkdir(parents=True, exist_ok=True)
    for theme in COLOURS:
        for name, box in CROPS.items():
            with Image.open(folder / f"{name}-{theme}.png") as image:
                if image.size != (1280, 720):
                    raise ValueError("Capture at 1280 x 720 before cropping.")
                image.crop(box).save(FRAMES / f"{name}-{theme}.png", optimize=True)


def picture(name: str, theme: str, x: int, y: int, width: int, height: int) -> str:
    data = base64.b64encode((FRAMES / f"{name}-{theme}.png").read_bytes()).decode()
    return (
        f'<image x="{x}" y="{y}" width="{width}" height="{height}" '
        f'href="data:image/png;base64,{data}"/>'
    )


def words(text: str, x: int, y: int, size: int, colour: str, weight: int = 400) -> str:
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
        f'fill="{colour}">{escape(text)}</text>'
    )


def svg(body: str, height: int, title: str, description: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="880" height="{height}" '
        f'viewBox="0 0 880 {height}" role="img" aria-labelledby="title description">\n'
        f'<title id="title">{escape(title)}</title>\n'
        f'<desc id="description">{escape(description)}</desc>\n'
        f'<g font-family="Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif">'
        f"{body}</g>\n</svg>\n"
    )


def walkthrough(theme: str) -> str:
    bg, ink, muted, accent, line = COLOURS[theme]
    scenes = (
        ("start", "Bring a server into Kitden.", "Start with docs, connected only to Claude Code."),
        (
            "preview",
            "See the change before it happens.",
            "The dashed card is a preview. Nothing is written yet.",
        ),
        ("review", "Check who gets access.", "Open Show changes to review the move."),
        (
            "applied",
            "One server. Three connected clients.",
            "Apply saves a backup, makes the change and checks it.",
        ),
    )
    css = """
    .scene { opacity: 0; }
    .s3 { opacity: 1; }
    .s0 { animation: first 20s linear infinite; }
    .s1 { animation: second 20s linear infinite; }
    .s2 { animation: third 20s linear infinite; }
    .s3 { animation: fourth 20s linear infinite; }
    @keyframes first { 0%,14%,100% { opacity:1 } 15%,99% { opacity:0 } }
    @keyframes second { 0%,14%,35%,100% { opacity:0 } 15%,34% { opacity:1 } }
    @keyframes third { 0%,34%,57%,100% { opacity:0 } 35%,56% { opacity:1 } }
    @keyframes fourth { 0%,56%,100% { opacity:0 } 57%,99% { opacity:1 } }
    @media (prefers-reduced-motion: reduce) {
      .scene { animation:none; opacity:0; }
      .s3 { opacity:1; }
    }
    """
    body = f"<style>{css}</style>"
    for i, (name, title, subtitle) in enumerate(scenes):
        body += f'<g class="scene s{i}"><rect width="880" height="560" rx="12" fill="{bg}"/>'
        body += words(title, 30, 39, 24, ink, 600)
        body += words(subtitle, 30, 66, 15, muted)
        body += words(f"{i + 1} / 4", 809, 39, 14, accent, 500)
        if name == "review":
            body += picture(name, theme, 478, 88, 340, 413)
            body += words("Your call, every time.", 42, 217, 25, ink, 600)
            for j, text in enumerate(
                (
                    "See which clients are affected.",
                    "Inspect the exact file changes.",
                    "Apply when you are ready.",
                )
            ):
                body += words(text, 42, 260 + j * 30, 17, muted)
        else:
            body += picture(name, theme, 106, 86, 668, 422)
        body += f'<path d="M30 520H850" stroke="{line}"/>'
        body += words(
            "Sample setup · Changes take effect in new client sessions.", 30, 544, 13, muted
        )
        body += "</g>"
    return svg(
        body,
        560,
        "Move, preview, review, apply",
        "Real demo states: docs starts in Claude Code, waits in preview, is reviewed, then joins "
        "the gateway for Claude Code, Codex and Cursor. Apply keeps a backup for Undo.",
    )


def library(theme: str) -> str:
    bg = COLOURS[theme][0]
    body = f'<rect width="880" height="215" rx="12" fill="{bg}"/>'
    body += picture("library", theme, 16, 20, 848, 169)
    return svg(
        body,
        215,
        "See what each client loads",
        "The Library filtered to review: pr-review "
        "is off in Claude Code and Cursor; code-review is on in Codex and Cursor.",
    )


def undo(theme: str) -> str:
    bg, ink, muted, _, _ = COLOURS[theme]
    body = f'<rect width="880" height="260" rx="12" fill="{bg}"/>'
    body += words("Apply keeps a backup.", 30, 36, 19, ink, 500)
    body += picture("history", theme, 28, 50, 824, 74)
    body += words("Undo puts it back.", 30, 164, 19, muted, 500)
    body += picture("undone", theme, 28, 178, 824, 74)
    return svg(
        body,
        260,
        "A change, then Undo",
        "The same real change before and after Undo. "
        "The applied row has an Undo button; the restored change is marked Undone.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path)
    args = parser.parse_args()
    if args.captures:
        crop_captures(args.captures)
    for theme in COLOURS:
        suffix = "-dark" if theme == "dark" else ""
        for name, build in (("walkthrough", walkthrough), ("compare", library), ("undo", undo)):
            (OUT / f"{name}{suffix}.svg").write_text(build(theme))


if __name__ == "__main__":
    main()
