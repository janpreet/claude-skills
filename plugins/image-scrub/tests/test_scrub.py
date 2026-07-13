#!/usr/bin/env python3
"""Functional tests for the image-scrub scrubber.

Uses Pillow to build real images with real EXIF and to verify afterwards
that metadata is gone and pixels are byte-for-byte unchanged. Pillow is a
TEST-only dependency; the scrubber itself is pure stdlib. Also exercises
the installable native git pre-commit hook end to end.

Run:  python3 tests/test_scrub.py     (exit 0 = all passed)
"""
import os
import struct
import subprocess
import sys
import tempfile

from PIL import Image
from PIL.ExifTags import Base as ExifTag

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
STRIPPER = os.path.join(SCRIPTS, "strip_image_metadata.py")

failures = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL") + " " + name + (" — " + detail if detail and not cond else ""))
    if not cond:
        failures.append(name)


def strip(*paths):
    return subprocess.run(
        [sys.executable, STRIPPER, *paths], capture_output=True, text=True
    ).stdout.strip()


def make_exif():
    exif = Image.Exif()
    exif[ExifTag.Make.value] = "Apple"
    exif[ExifTag.Model.value] = "iPhone 15"
    exif[ExifTag.Software.value] = "18.0"
    # GPS IFD — the headline privacy leak.
    exif[ExifTag.GPSInfo.value] = {
        1: "N", 2: (43.0, 30.0, 0.0),
        3: "W", 4: (79.0, 23.0, 0.0),
    }
    return exif


def test_jpeg(d):
    src = Image.new("RGB", (8, 8), (200, 40, 40))
    before = list(src.getdata())
    p = os.path.join(d, "photo.jpg")
    src.save(p, "JPEG", exif=make_exif(), quality=95)
    # Append XMP APP1, a COM comment, and trailing junk after EOI.
    with open(p, "rb") as f:
        data = f.read()
    xmp = b"http://ns.adobe.com/xap/1.0/\x00<x:xmpmeta>home address</x:xmpmeta>"
    app1 = b"\xff\xe1" + struct.pack(">H", len(xmp) + 2) + xmp
    com = b"\xff\xfe\x00\x10secret-comment"
    with open(p, "wb") as f:
        f.write(data[:2] + app1 + com + data[2:] + b"TRAILING-PAYLOAD")

    check("jpeg carries metadata before", b"Exif" in open(p, "rb").read())
    out = strip(p)
    check("jpeg reported SCRUBBED", out.startswith("SCRUBBED"), out)
    after = open(p, "rb").read()
    check("jpeg EXIF gone", b"Exif" not in after)
    check("jpeg XMP gone", b"xmpmeta" not in after)
    check("jpeg comment gone", b"secret-comment" not in after)
    check("jpeg trailing payload gone", b"TRAILING-PAYLOAD" not in after)
    reopened = Image.open(p)
    check("jpeg still decodes", reopened.size == (8, 8))
    check("jpeg exif empty after", not dict(reopened.getexif()))
    check("jpeg pixels unchanged", list(reopened.getdata()) == before)


def test_png(d):
    src = Image.new("RGB", (8, 8), (30, 160, 90))
    before = list(src.getdata())
    p = os.path.join(d, "pic.png")
    exif = make_exif()
    src.save(p, "PNG", exif=exif, pnginfo=_pnginfo())
    check("png carries text/exif before",
          any(m in open(p, "rb").read() for m in (b"eXIf", b"Author", b"secret")))
    out = strip(p)
    check("png reported SCRUBBED", out.startswith("SCRUBBED"), out)
    after = open(p, "rb").read()
    check("png eXIf gone", b"eXIf" not in after)
    check("png tEXt gone", b"Author" not in after and b"secret-note" not in after)
    reopened = Image.open(p)
    check("png still decodes", reopened.size == (8, 8))
    check("png pixels unchanged", list(reopened.getdata()) == before)


def _pnginfo():
    from PIL.PngImagePlugin import PngInfo
    info = PngInfo()
    info.add_text("Author", "Janpreet Singh")
    info.add_text("Comment", "secret-note home addr")
    return info


def test_webp(d):
    src = Image.new("RGB", (8, 8), (60, 60, 220))
    before = list(src.getdata())
    p = os.path.join(d, "img.webp")
    src.save(p, "WEBP", exif=make_exif(), lossless=True)
    check("webp carries exif before", b"EXIF" in open(p, "rb").read())
    out = strip(p)
    check("webp reported SCRUBBED/CLEAN", out.split("\t")[0] in ("SCRUBBED", "CLEAN"), out)
    after = open(p, "rb").read()
    check("webp EXIF chunk gone", b"Exif\x00\x00" not in after)
    # RIFF size field must match actual byte length, else the file is corrupt.
    riff_size = struct.unpack("<I", after[4:8])[0]
    check("webp RIFF size correct", riff_size == len(after) - 8, f"{riff_size} vs {len(after)-8}")
    reopened = Image.open(p)
    check("webp still decodes", reopened.size == (8, 8))
    check("webp pixels unchanged", list(reopened.getdata()) == before)


def test_idempotent(d):
    p = os.path.join(d, "again.jpg")
    Image.new("RGB", (4, 4), (1, 2, 3)).save(p, "JPEG", exif=make_exif())
    strip(p)
    out = strip(p)  # second pass: nothing left to remove
    check("second pass is CLEAN", out.startswith("CLEAN"), out)


def test_unsupported(d):
    p = os.path.join(d, "notes.txt")
    with open(p, "wb") as f:
        f.write(b"just text")
    out = strip(p)
    check("non-image reported UNSUPPORTED", out.startswith("UNSUPPORTED"), out)


def test_git_hook(d):
    repo = os.path.join(d, "repo")
    os.makedirs(repo)
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run([os.path.join(SCRIPTS, "install-git-hook.sh"), repo],
                   check=True, capture_output=True)
    img = os.path.join(repo, "with space.jpg")
    Image.new("RGB", (6, 6), (9, 9, 9)).save(img, "JPEG", exif=make_exif())
    subprocess.run(["git", "add", "."], cwd=repo, check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "add"], cwd=repo, check=True, env=env)
    blob = subprocess.run(["git", "show", "HEAD:with space.jpg"],
                          cwd=repo, capture_output=True, env=env).stdout
    check("committed blob has no EXIF", b"Exif" not in blob)


def main():
    with tempfile.TemporaryDirectory() as d:
        test_jpeg(d)
        test_png(d)
        test_webp(d)
        test_idempotent(d)
        test_unsupported(d)
        test_git_hook(d)
    print()
    if failures:
        print(f"{len(failures)} FAILED: {failures}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
