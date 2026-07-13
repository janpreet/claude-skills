#!/bin/bash
# Strip metadata from every image staged for commit, then re-stage the
# scrubbed files. Usage: scrub-staged.sh [repo-dir]
# Note: re-staging uses the working-tree file, so a partially staged image
# will have its full working-tree content staged after scrubbing.
set -u
DIR="${1:-.}"
STRIPPER="$(cd "$(dirname "$0")" && pwd)/strip_image_metadata.py"

cd "$DIR" 2>/dev/null || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

staged=()
while IFS= read -r -d '' f; do
  case "$(printf '%s' "$f" | tr '[:upper:]' '[:lower:]')" in
    *.jpg|*.jpeg|*.png|*.webp|*.gif|*.tif|*.tiff|*.heic|*.heif|*.avif)
      [ -f "$f" ] && staged+=("$f") ;;
  esac
done < <(git diff --cached --name-only --diff-filter=ACM -z)

[ "${#staged[@]}" -eq 0 ] && exit 0

while IFS=$'\t' read -r status f rest; do
  case "$status" in
    SCRUBBED)
      git add -- "$f"
      echo "image-scrub: stripped metadata from $f" ;;
    UNSUPPORTED)
      echo "image-scrub: WARNING: cannot scrub $f without exiftool (brew install exiftool)" >&2 ;;
    ERROR)
      echo "image-scrub: WARNING: failed on $f: $rest" >&2 ;;
  esac
done < <(python3 "$STRIPPER" "${staged[@]}")

exit 0
