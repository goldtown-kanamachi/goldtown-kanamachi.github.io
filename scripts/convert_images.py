#!/usr/bin/env python3
"""images/ 内の jpg/png を WebP に変換して「元ファイル名 + .webp」で追加する。

使い方:  python3 scripts/convert_images.py   (要 Pillow: pip install Pillow)

設計原則:
- 原本(jpg/png)は上書き・削除しない。WebPは別名で追加するだけ。
- 「元名 + .webp」方式なのは、room-402-10.jpg と room-402-10.png のように
  拡張子違いの同名ファイルが存在し、単純な拡張子置換では衝突するため。
- 変換結果は data/image_cache.json(原本のSHA-1)でキャッシュし、
  原本が変わらない限り再変換しない。
- EXIFの回転情報は変換時にピクセルへ反映する(WebPで向きが狂わないように)。
"""
import hashlib
import json
import sys
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("ERROR: Pillow が必要です。 pip install Pillow を実行してください。")

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "images"
CACHE_PATH = ROOT / "data" / "image_cache.json"
QUALITY = 80
SOURCE_SUFFIXES = (".jpg", ".jpeg", ".png")


def sha1_of(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def main() -> int:
    try:
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        cache = {}
    new_cache = {}
    converted, skipped = 0, 0
    for src in sorted(IMAGES.iterdir()):
        if src.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        rel = f"images/{src.name}"
        digest = sha1_of(src)
        out = src.with_name(src.name + ".webp")
        if cache.get(rel) == digest and out.is_file():
            new_cache[rel] = digest
            skipped += 1
            continue
        im = Image.open(src)
        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "LA", "PA"):
            im = im.convert("RGBA")
        elif im.mode != "RGB":
            im = im.convert("RGB")
        im.save(out, "WEBP", quality=QUALITY, method=6)
        new_cache[rel] = digest
        converted += 1
    CACHE_PATH.write_text(
        json.dumps(new_cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"webp: 変換 {converted} 件 / キャッシュ利用 {skipped} 件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
