#!/usr/bin/env python3
"""data/rooms.json の入力漏れ・誤りと、生成済みページの整合を検査する。

使い方:  python3 scripts/validate.py
終了コード: 0 = 問題なし / 1 = エラーあり(公開を止める)

検査内容:
1. rooms.json の入力漏れ・形式誤り・画像ファイルの存在
2. 客室個別ページ(rooms/)の整合:
   - activeな部屋の日英ページが存在し、activeでない部屋のページが残っていないこと
   - トップ両ページから各個別ページへのリンクがあること(非activeへのリンクが無いこと)
   - 各HTMLが参照する画像(src / srcset)・ローカルリンクが実在すること
   - 個別ページの canonical / hreflang(en・ja・x-default)が相互に正しいこと
   - sitemap.xml にactiveな個別ページが載り、非activeが載っていないこと

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


def check_generated_pages(data: dict) -> None:
    """生成済みHTML(トップ2+個別ページ)とsitemapの整合検査。"""
    rooms = [r for r in data.get("rooms", []) if isinstance(r, dict)]
    active = [r for r in rooms if r.get("active")]
    inactive = [r for r in rooms if not r.get("active")]
    base = str(data.get("site", {}).get("base_url", "")).rstrip("/")
    rooms_dir = ROOT / "rooms"

    # 1) 個別ページの存在(active=あり / 非active=なし)
    expected = set()
    for r in active:
        num = r.get("room_number", "")
        for name in (f"{num}.html", f"{num}-ja.html"):
            expected.add(name)
            if not (rooms_dir / name).is_file():
                err(f"rooms/{name} がありません。scripts/generate.py を実行してください")
    if rooms_dir.is_dir():
        for p in sorted(rooms_dir.glob("*.html")):
            if p.name not in expected:
                err(f"rooms/{p.name} は現在activeな部屋のページではありません。scripts/generate.py を再実行して削除してください")

    # 2) HTMLの画像参照・ローカルリンク検査
    html_files = [ROOT / "index.html", ROOT / "ja.html"]
    if rooms_dir.is_dir():
        html_files += sorted(rooms_dir.glob("*.html"))
    for hf in html_files:
        if not hf.is_file():
            err(f"{hf.name} がありません。scripts/generate.py を実行してください")
            continue
        html = hf.read_text(encoding="utf-8")
        rel = hf.relative_to(ROOT)
        for m in re.finditer(r'(?:src|srcset)="([^"]+)"', html):
            url = m.group(1)
            if url.startswith(("http://", "https://", "data:")):
                continue
            if not (hf.parent / url).is_file():
                err(f"{rel}: 参照画像が存在しません: {url}")
        for m in re.finditer(r'href="([^"#]+\.html)(?:#[^"]*)?"', html):
            url = m.group(1)
            if url.startswith(("http://", "https://")):
                continue
            if not (hf.parent / url).is_file():
                err(f"{rel}: リンク先が存在しません: {url}")

    # 3) トップ両ページから個別ページへのリンク
    for page, suffix in (("index.html", ".html"), ("ja.html", "-ja.html")):
        p = ROOT / page
        if not p.is_file():
            continue
        html = p.read_text(encoding="utf-8")
        for r in active:
            num = r.get("room_number", "")
            if f'href="rooms/{num}{suffix}"' not in html:
                err(f"{page}: {num}号室の個別ページ(rooms/{num}{suffix})へのリンクがありません")
        for r in inactive:
            num = r.get("room_number", "")
            if f"rooms/{num}.html" in html or f"rooms/{num}-ja.html" in html:
                err(f"{page}: activeでない{num}号室の個別ページへのリンクが残っています")

    # 4) 個別ページの canonical / hreflang 相互整合
    for r in active:
        num = r.get("room_number", "")
        en_url = f"{base}/rooms/{num}.html"
        ja_url = f"{base}/rooms/{num}-ja.html"
        for name, canonical in ((f"{num}.html", en_url), (f"{num}-ja.html", ja_url)):
            p = rooms_dir / name
            if not p.is_file():
                continue
            html = p.read_text(encoding="utf-8")
            if f'<link rel="canonical" href="{canonical}">' not in html:
                err(f"rooms/{name}: canonical が {canonical} ではありません")
            for hreflang, url in (("en", en_url), ("ja", ja_url), ("x-default", en_url)):
                if f'<link rel="alternate" hreflang="{hreflang}" href="{url}">' not in html:
                    err(f"rooms/{name}: hreflang={hreflang} が {url} を指していません")

    # 5) sitemap.xml の個別ページ整合
    sm_path = ROOT / "sitemap.xml"
    if sm_path.is_file():
        sm = sm_path.read_text(encoding="utf-8")
        for r in active:
            num = r.get("room_number", "")
            for url in (f"{base}/rooms/{num}.html", f"{base}/rooms/{num}-ja.html"):
                if f"<loc>{url}</loc>" not in sm:
                    err(f"sitemap.xml: {url} がありません。scripts/generate.py を実行してください")
        for r in inactive:
            num = r.get("room_number", "")
            if f"/rooms/{num}.html" in sm or f"/rooms/{num}-ja.html" in sm:
                err(f"sitemap.xml: activeでない{num}号室のURLが残っています")
    else:
        err("sitemap.xml がありません。scripts/generate.py を実行してください")


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

    check_generated_pages(data)

    if errors:
        print(f"NG: {len(errors)}件の問題があります", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"OK: rooms.json 検査合格 (部屋 {len(rooms)}室 / 営業中 {active_count}室)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
