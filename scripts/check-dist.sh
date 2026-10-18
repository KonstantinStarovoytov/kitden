#!/usr/bin/env bash
# Checks the built files in dist/: the wheel holds the page's files and the source distribution
# holds only the package. The release workflow runs it. Usage: scripts/check-dist.sh dist
set -euo pipefail
dist="${1:-dist}"

if ! unzip -l "$dist"/*.whl | grep kitden/web/static/index.html >/dev/null; then
  echo "The wheel misses kitden/web/static/index.html"
  exit 1
fi
extra="$(tar tzf "$dist"/*.tar.gz | grep -E '^kitden-[^/]+/(tests|docs|specs)/' || true)"
if [ -n "$extra" ]; then
  echo "The source distribution holds files that do not belong in it:"
  echo "$extra"
  exit 1
fi
echo "Built files ok"
