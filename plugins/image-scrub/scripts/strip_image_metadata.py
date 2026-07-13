#!/usr/bin/env python3
"""Strip metadata (EXIF, GPS, XMP, IPTC, comments) from images, in place.

Zero dependencies: pure-stdlib parsers for JPEG, PNG and WebP. If exiftool
is installed it is used instead (and also covers TIFF/HEIC/AVIF/GIF).
ICC color profiles are kept so images render identically.

Usage: strip_image_metadata.py FILE [FILE...]
Prints one line per file:  SCRUBBED|CLEAN|UNSUPPORTED|ERROR <tab> path
Exit 0 unless a file errored.
"""
import shutil
import struct
import subprocess
import sys

# ---------------------------------------------------------------- JPEG
# Keep APP0 (JFIF), APP2 (ICC profile), APP14 (Adobe color transform).
# Drop every other APPn (EXIF/XMP/IPTC/Photoshop/...) and COM segments,
# plus anything trailing after EOI (e.g. embedded motion-photo videos).
_JPEG_KEEP = {0xE0, 0xE2, 0xEE}


def strip_jpeg(data: bytes) -> bytes:
    if data[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG")
    out = bytearray(b"\xff\xd8")
    i = 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            raise ValueError("bad JPEG marker at %d" % i)
        marker = data[i + 1]
        if marker == 0xDA:  # SOS: entropy data follows, copy through EOI
            end = data.find(b"\xff\xd9", i)
            end = len(data) if end == -1 else end + 2
            out += data[i:end]
            return bytes(out)
        if marker == 0xD9:
            break
        seglen = struct.unpack(">H", data[i + 2 : i + 4])[0]
        seg = data[i : i + 2 + seglen]
        is_meta = (0xE0 <= marker <= 0xEF and marker not in _JPEG_KEEP) or marker == 0xFE
        if not is_meta:
            out += seg
        i += 2 + seglen
    out += b"\xff\xd9"
    return bytes(out)


# ----------------------------------------------------------------- PNG
# Whitelist: structural chunks plus the ones that affect rendering (color,
# transparency, APNG animation). Everything else — tEXt/zTXt/iTXt, eXIf,
# tIME, private chunks — is metadata and gets dropped.
_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_PNG_KEEP = {
    b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"gAMA", b"cHRM",
    b"sRGB", b"iCCP", b"sBIT", b"bKGD", b"pHYs", b"acTL", b"fcTL", b"fdAT",
}


def strip_png(data: bytes) -> bytes:
    if data[:8] != _PNG_SIG:
        raise ValueError("not a PNG")
    out = bytearray(_PNG_SIG)
    i = 8
    while i + 8 <= len(data):
        length = struct.unpack(">I", data[i : i + 4])[0]
        ctype = data[i + 4 : i + 8]
        chunk_end = i + 12 + length
        if ctype in _PNG_KEEP:
            out += data[i:chunk_end]
        if ctype == b"IEND":
            break
        i = chunk_end
    return bytes(out)


# ---------------------------------------------------------------- WebP
def strip_webp(data: bytes) -> bytes:
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("not a WebP")
    out = bytearray(data[:12])
    i = 12
    while i + 8 <= len(data):
        fourcc = data[i : i + 4]
        size = struct.unpack("<I", data[i + 4 : i + 8])[0]
        chunk_end = i + 8 + size + (size & 1)  # chunks are padded to even
        if fourcc not in (b"EXIF", b"XMP "):
            chunk = bytearray(data[i:chunk_end])
            if fourcc == b"VP8X" and size >= 1:
                chunk[8] &= ~0x0C  # clear the EXIF (0x08) and XMP (0x04) flags
            out += chunk
        i = chunk_end
    struct.pack_into("<I", out, 4, len(out) - 8)
    return bytes(out)


_HANDLERS = (
    (b"\xff\xd8", strip_jpeg),
    (_PNG_SIG, strip_png),
    (b"RIFF", strip_webp),
)


def scrub(path: str) -> str:
    """Returns SCRUBBED, CLEAN or UNSUPPORTED."""
    with open(path, "rb") as f:
        data = f.read()
    for magic, handler in _HANDLERS:
        if data[: len(magic)] == magic:
            cleaned = handler(data)
            if cleaned == data:
                return "CLEAN"
            with open(path, "wb") as f:
                f.write(cleaned)
            return "SCRUBBED"
    return "UNSUPPORTED"


def scrub_exiftool(paths):
    # -all= wipes every metadata group; --icc_profile:all excludes the ICC
    # color profile from deletion so rendering is unchanged.
    before = {p: open(p, "rb").read() for p in paths}
    subprocess.run(
        ["exiftool", "-all=", "--icc_profile:all", "-overwrite_original", "-q", "-q", *paths],
        check=False,
    )
    for p in paths:
        with open(p, "rb") as f:
            changed = f.read() != before[p]
        print(("SCRUBBED" if changed else "CLEAN") + "\t" + p)


def main(argv):
    if not argv:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    if shutil.which("exiftool"):
        scrub_exiftool(argv)
        return 0
    status = 0
    for path in argv:
        try:
            print(scrub(path) + "\t" + path)
        except (OSError, ValueError) as e:
            print("ERROR\t%s\t%s" % (path, e))
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
