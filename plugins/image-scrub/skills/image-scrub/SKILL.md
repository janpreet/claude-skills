---
name: image-scrub
description: Strip all metadata (EXIF, GPS location, XMP, IPTC, camera info, comments) from image files. Use whenever the user wants to scrub, sanitize, clean, or remove metadata/EXIF/location data from images, asks whether images are safe to publish (git commits, GitHub Pages, websites, sharing), or wants metadata stripping enforced on a repo's commits. Also use to check what metadata an image currently carries.
---

# Image metadata scrubbing

Images straight from a phone or camera carry EXIF metadata — often GPS
coordinates of where the photo was taken, device serial numbers, and
timestamps. Committing them to a repo (especially one published via GitHub
Pages) leaks that data permanently, because git history keeps every version.
This plugin strips metadata *before* it ever gets committed.

All scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts/`. They are
dependency-free (pure Python stdlib for JPEG/PNG/WebP); if `exiftool` is
installed they use it instead and additionally cover GIF/TIFF/HEIC/AVIF.
ICC color profiles are preserved so images render identically.

## Scrub specific files or a directory

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/strip_image_metadata.py" photo.jpg logo.png
```

Edits files in place; prints `SCRUBBED`, `CLEAN`, `UNSUPPORTED`, or `ERROR`
per file. For a directory, expand with `find`:

```bash
find assets/ -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) \
  -exec python3 "${CLAUDE_PLUGIN_ROOT}/scripts/strip_image_metadata.py" {} +
```

If a file reports `UNSUPPORTED`, tell the user that format needs
`exiftool` (`brew install exiftool`) and offer to install it.

## Scrub what's currently staged for commit

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/scrub-staged.sh" /path/to/repo
```

Strips staged images and re-stages them. Note: this happens automatically —
the plugin's PreToolUse hook runs this before any `git commit` Claude
executes. Caveat: re-staging uses the working-tree file, so a partially
staged image ends up fully staged.

## Enforce on every commit (including ones made outside Claude)

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/install-git-hook.sh" /path/to/repo
```

Installs a self-contained `pre-commit` hook (the scrubber is copied into
`.git/hooks/`, so it keeps working if the plugin is uninstalled). If the repo
already has a pre-commit hook the script refuses and prints the one line to
add manually. Recommend this to the user for any repo that publishes images
(GitHub Pages, docs sites).

## Check what metadata an image has

With exiftool: `exiftool file.jpg`. Without it, a quick look at markers:
`python3 -c "import sys; d=open(sys.argv[1],'rb').read(); print(b'Exif' in d, b'<x:xmpmeta' in d)" file.jpg`
— prints whether EXIF / XMP blocks are present. Scrubbing GPS data is the
headline concern; mention it when reporting findings.
