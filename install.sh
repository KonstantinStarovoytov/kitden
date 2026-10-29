#!/bin/sh
# Installs Kitden on macOS: uv when it is missing, then Kitden as a uv tool, then opens the page.
# One line:  curl -LsSf https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/install.sh | sh
# It never changes anything in Claude Code, Codex or Cursor. Running it again updates Kitden
# when a newer release is named below.
set -eu

KITDEN_REF="v0.3.0"
KITDEN_SOURCE="git+https://github.com/KonstantinStarovoytov/kitden@$KITDEN_REF"
FOLLOW_UP="https://github.com/KonstantinStarovoytov/kitden#linux-and-windows"

# 1. Only macOS for now.
if [ "$(uname -s)" != "Darwin" ]; then
  echo "Kitden runs on macOS today. Linux and Windows are coming: $FOLLOW_UP. Nothing was installed." >&2
  exit 1
fi

# 2. Find uv, or install it with uv's own installer.
uv_default="${XDG_BIN_HOME:-$HOME/.local/bin}/uv"
if command -v uv >/dev/null 2>&1; then
  uv="uv"
elif [ -x "$uv_default" ]; then
  uv="$uv_default"
else
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh || true
  uv="$uv_default"
  if [ ! -x "$uv" ]; then
    echo "Could not install uv. See https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 2
  fi
fi

# 3. Install or update Kitden in its own environment. Until Kitden is on PyPI, uv fetches it from
#    the repository and needs git, which comes with the macOS command line tools.
if ! xcode-select -p >/dev/null 2>&1; then
  echo "Kitden needs git until it is on PyPI. Run: xcode-select --install, then run this line again." >&2
  exit 3
fi
echo "Installing Kitden..."
if ! "$uv" tool install "$KITDEN_SOURCE"; then
  echo "Could not install Kitden. See the uv output above." >&2
  exit 3
fi

# 4. Open the page. The command returns at once and prints the link.
bin="$("$uv" tool dir --bin)"
echo "Opening the Kitden page..."
"$bin/kitden"
echo "Kitden is installed: $bin/kitden"

# 5. Say how to get the kitden command on PATH when it is not there yet.
case ":$PATH:" in
  *":$bin:"*) ;;
  *) echo "To use the kitden command from any terminal, run: $uv tool update-shell, then open a new terminal." ;;
esac
