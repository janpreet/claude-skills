#!/bin/bash
# Install a self-contained pre-commit hook into a repo so images are
# scrubbed on EVERY commit, not just ones made through Claude Code.
# Usage: install-git-hook.sh [repo-dir]
set -eu
DIR="${1:-.}"
HERE="$(cd "$(dirname "$0")" && pwd)"

cd "$DIR"
HOOKS="$(git rev-parse --git-path hooks)"
mkdir -p "$HOOKS"

if [ -e "$HOOKS/pre-commit" ] && ! grep -q image-scrub "$HOOKS/pre-commit" 2>/dev/null; then
  echo "image-scrub: $HOOKS/pre-commit already exists and isn't ours." >&2
  echo "Add this line to it manually:" >&2
  echo "  \"\$(git rev-parse --git-path hooks)/image-scrub-staged.sh\" \"\$(git rev-parse --show-toplevel)\"" >&2
  exit 1
fi

# Copy the scrubber next to the hook so it keeps working even if the
# plugin is moved, updated or uninstalled.
cp "$HERE/strip_image_metadata.py" "$HOOKS/strip_image_metadata.py"
cp "$HERE/scrub-staged.sh" "$HOOKS/image-scrub-staged.sh"
cat > "$HOOKS/pre-commit" <<'EOF'
#!/bin/bash
# image-scrub: strip metadata from staged images before committing
"$(git rev-parse --git-path hooks)/image-scrub-staged.sh" "$(git rev-parse --show-toplevel)"
EOF
chmod +x "$HOOKS/pre-commit" "$HOOKS/image-scrub-staged.sh" "$HOOKS/strip_image_metadata.py"
echo "image-scrub: installed pre-commit hook in $HOOKS"
