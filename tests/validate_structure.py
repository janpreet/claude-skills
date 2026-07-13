#!/usr/bin/env python3
"""Validate the marketplace + plugin + skill structure.

Catches the mistakes that break a marketplace silently: malformed JSON, a
plugin listed in the marketplace whose folder or manifest is missing, a
name mismatch, or a skill without the frontmatter Claude needs to trigger
it. Pure stdlib so CI needs no dependencies.

Run from repo root:  python3 tests/validate_structure.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
errors = []


def err(msg):
    errors.append(msg)


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        err(f"missing file: {rel(path)}")
    except json.JSONDecodeError as e:
        err(f"invalid JSON in {rel(path)}: {e}")
    return None


def rel(path):
    return os.path.relpath(path, ROOT)


def parse_frontmatter(path):
    """Return the frontmatter block's key set, or None if absent/malformed."""
    with open(path) as f:
        text = f.read()
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    keys = set()
    for line in text[3:end].splitlines():
        if line and not line[0].isspace() and ":" in line:
            keys.add(line.split(":", 1)[0].strip())
    return keys


def validate_skill(skill_dir):
    md = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(md):
        err(f"skill missing SKILL.md: {rel(skill_dir)}")
        return
    keys = parse_frontmatter(md)
    if keys is None:
        err(f"{rel(md)}: missing or malformed YAML frontmatter")
        return
    for required in ("name", "description"):
        if required not in keys:
            err(f"{rel(md)}: frontmatter missing '{required}'")


def validate_plugin(source):
    pdir = os.path.join(ROOT, source)
    if not os.path.isdir(pdir):
        err(f"plugin source not found: {source}")
        return
    manifest = load_json(os.path.join(pdir, ".claude-plugin", "plugin.json"))
    if manifest is None:
        return
    if "name" not in manifest:
        err(f"{source}/.claude-plugin/plugin.json: missing 'name'")
    skills_root = os.path.join(pdir, "skills")
    if os.path.isdir(skills_root):
        for entry in sorted(os.listdir(skills_root)):
            sub = os.path.join(skills_root, entry)
            if os.path.isdir(sub):
                validate_skill(sub)
    return manifest.get("name")


def main():
    market = load_json(os.path.join(ROOT, ".claude-plugin", "marketplace.json"))
    if market is None:
        print("\n".join(errors))
        return 1
    for field in ("name", "plugins"):
        if field not in market:
            err(f"marketplace.json: missing '{field}'")
    for entry in market.get("plugins", []):
        source = entry.get("source")
        listed = entry.get("name")
        if not source:
            err(f"marketplace plugin entry missing 'source': {entry}")
            continue
        actual = validate_plugin(source)
        if listed and actual and listed != actual:
            err(f"name mismatch for {source}: marketplace says '{listed}', "
                f"manifest says '{actual}'")
    if errors:
        for e in errors:
            print("ERROR: " + e)
        print(f"\n{len(errors)} problem(s) found")
        return 1
    print("structure OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
