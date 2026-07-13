# claude-skills

A small personal marketplace of [Claude Code](https://claude.com/claude-code)
plugins and skills — little quality-of-life tools, one plugin per folder
under `plugins/`.

## Install

```
/plugin marketplace add janpreet/claude-skills
/plugin install image-scrub@claude-skills
```

## Plugins

### image-scrub

Strips **all metadata** — EXIF, GPS location, XMP, IPTC, camera info,
comments — from images before they leave in a git commit (think GitHub
Pages, docs sites, anything public). Git history keeps every version of a
file forever, so the only safe moment to scrub is *before* the commit.

Three layers of protection:

| Layer | What it covers |
|---|---|
| PreToolUse hook | Every `git commit` Claude Code runs — staged images are scrubbed and re-staged automatically |
| `image-scrub` skill | On-demand: "strip the metadata from these photos", "is this image safe to publish?" |
| `install-git-hook.sh` | Installs a self-contained native `pre-commit` hook, so commits made outside Claude are covered too |

The scrubber is dependency-free (pure Python stdlib) for JPEG, PNG and
WebP, and preserves ICC color profiles so images render identically. If
`exiftool` is installed it is used instead, extending coverage to GIF,
TIFF, HEIC and AVIF.

## License

MIT
