#!/usr/bin/env python3
"""data/rooms.json の入力漏れ・誤りを検査する。

使い方:  python3 scripts/validate.py
終了コード: 0 = 問題なし / 1 = エラーあり(公開を止める)

依存ライブラリなし(Python 3 標準ライブラリのみ)。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
errors = []


def err(msg: str) -> None:
    errors.append(msg)


def main() -> int:
    path = ROOT / "data" / "rooms.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: rooms.json が読めません: {e}", file=sys.stderr)
        return 1

    # site
    site = data.get("site", {})
    if not str(site.get("base_url", "")).startswith("https://"):
        err("site.base_url は https:// で始まる必要があります")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(site.get("last_updated", ""))):
        err("site.last_updated は YYYY-MM-DD 形式で入力してください")
    if not re.fullmatch(r"G-[A-Z0-9]+", str(site.get("ga4_measurement_id", ""))):
        err("site.ga4_measurement_id が G-XXXX 形式ではありません")
    for lang in ("en", "ja"):
        seo = site.get("seo", {}).get(lang, {})
        for key in ("meta_description", "og_description"):
            if not seo.get(key):
                err(f"site.seo.{lang}.{key} が未入力です")

    # legal
    legal = data.get("legal", {})
    if legal.get("display"):
        for k in ("facility_name", "operator_name", "license_type", "license_authority", "address"):
            if not legal.get(k):
                err(f"legal.display=true ですが legal.{k} が未入力です(未入力のままでは表示できません)")

    # rooms
    rooms = data.get("rooms", [])
    if not isinstance(rooms, list) or not rooms:
        err("rooms が空です")
        rooms = []
    seen = set()
    active_count = 0
    for i, r in enumerate(rooms):
        label = f"rooms[{i}] ({r.get('room_number', '?')}号室)"
        num = str(r.get("room_number", ""))
        if not re.fullmatch(r"\d+", num):
            err(f"{label}: room_number は数字のみで入力してください")
        if num in seen:
            err(f"{label}: room_number が重複しています")
        seen.add(num)
        if not isinstance(r.get("active"), bool):
            err(f"{label}: active は true/false で入力してください")
        if r.get("active"):
            active_count += 1
        if not isinstance(r.get("is_new"), bool):
            err(f"{label}: is_new は true/false で入力してください")
        if not isinstance(r.get("floor"), int) or r.get("floor", 0) < 1:
            err(f"{label}: floor は1以上の整数で入力してください")
        url = str(r.get("airbnb_url", ""))
        if not re.match(r"https://www\.airbnb\.(jp|com)/rooms/\d+$", url):
            err(f"{label}: airbnb_url が https://www.airbnb.jp/rooms/<数字> 形式ではありません")
        lic = r.get("license_number")
        if lic is not None and not str(lic).strip():
            err(f"{label}: license_number は null か空でない文字列にしてください")
        for lang in ("en", "ja"):
            loc = r.get(lang, {})
            if not loc.get("summary"):
                err(f"{label}: {lang}.summary が未入力です")
            tags = loc.get("tags")
            if not isinstance(tags, list) or not tags or not all(isinstance(t, str) and t for t in tags):
                err(f"{label}: {lang}.tags は1件以上の文字列リストで入力してください")
        photos = r.get("photos", {})
        main = photos.get("main", {})
        grid = photos.get("grid", [])
        all_photos = ([main] if main else []) + list(grid)
        if not main:
            err(f"{label}: photos.main が未入力です")
        if not isinstance(grid, list) or len(grid) < 1:
            err(f"{label}: photos.grid は1枚以上入力してください")
        for j, p in enumerate(all_photos):
            src = str(p.get("src", ""))
            where = f"{label}: photos[{'main' if j == 0 else j - 1}]"
            if not src.startswith("images/") and not re.fullmatch(r"[\w.-]+\.(jpg|jpeg|png|webp)", src):
                if not re.fullmatch(r"(images/)?[\w.-]+\.(jpg|jpeg|png|webp)", src):
                    err(f"{where}: src の形式が不正です: {src}")
            if not (ROOT / src).is_file():
                err(f"{where}: 画像ファイルが存在しません: {src}")
            for k in ("alt_en", "alt_ja"):
                if not p.get(k):
                    err(f"{where}: {k}(代替テキスト)が未入力です")
    if active_count == 0:
        err("activeな部屋が0件です。少なくとも1室は active: true にしてください")

    if errors:
        print(f"NG: {len(errors)}件の問題があります", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"OK: rooms.json 検査合格 (部屋 {len(rooms)}室 / 営業中 {active_count}室)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
