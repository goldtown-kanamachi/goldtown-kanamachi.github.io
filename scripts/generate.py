#!/usr/bin/env python3
"""rooms.json から index.html / ja.html / sitemap.xml / rooms/ 個別ページを生成する。

使い方:  python3 scripts/generate.py
入力:    data/rooms.json, templates/*.template.html
出力:    index.html, ja.html, sitemap.xml, rooms/<番号>.html, rooms/<番号>-ja.html

設計原則:
- 依存ライブラリなし(Python 3 標準ライブラリのみ)。
- 出力は決定的(同じ rooms.json からは常に同じバイト列)。
- active が false の部屋はページ・予約ボタン・個別ページ・sitemapから除外され、
  rooms/ 内の古い個別ページも自動で削除される。
- legal.display が false または未設定の間、法令表示ブロックは出力しない。
- 画像は「元名 + .webp」が存在する場合のみ <picture> でWebPを優先配信する
  (WebPが無い画像は従来どおり <img> のみ。scripts/convert_images.py で変換)。
- Airbnbボタンには GA4 明示イベント airbnb_click(room_numberパラメータ付き)を
  onclick で送信する(拡張計測の外部リンククリックイベントとは独立に両立)。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def esc(s: str) -> str:
    """HTML属性・テキスト用の最小エスケープ。"""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def join_en(items):
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def airbnb_onclick(num: str) -> str:
    """GA4明示イベント。room_number は数字のみ(validate.pyが保証)。"""
    return f" onclick=\"gtag('event','airbnb_click',{{room_number:'{num}'}})\""


def picture(src: str, alt: str, prefix: str = "") -> str:
    """WebP(元名+.webp)がある場合は <picture> でフォールバック付き配信。"""
    img = f'<img src="{prefix}{esc(src)}" alt="{esc(alt)}" loading="lazy">'
    if (ROOT / (src + ".webp")).is_file():
        return (
            f'<picture><source srcset="{prefix}{esc(src)}.webp" type="image/webp">'
            f"{img}</picture>"
        )
    return img


def room_article(room: dict, lang: str, prefix: str = "", detail_link: bool = True) -> str:
    num = room["room_number"]
    loc = room[lang]
    if lang == "en":
        h3 = f"Room {num}"
        badge = ' <span class="section-kicker">New</span>' if room["is_new"] else ""
        cta = f"View Room {num} on Airbnb"
        detail = f'<a href="rooms/{num}.html" class="btn outline">Room {num} details</a>'
        alt_key = "alt_en"
    else:
        h3 = f"{num}号室"
        badge = ' <span class="section-kicker">新規開業</span>' if room["is_new"] else ""
        cta = f"Airbnbで{num}号室を見る"
        detail = f'<a href="rooms/{num}-ja.html" class="btn outline">{num}号室の詳細</a>'
        alt_key = "alt_ja"
    tags = "".join(f"<span>{esc(t)}</span>" for t in loc["tags"])
    main = room["photos"]["main"]
    grid_lines = []
    for i, p in enumerate(room["photos"]["grid"]):
        line_prefix = "              " if i == 0 else ""
        grid_lines.append(
            f'{line_prefix}<figure>{picture(p["src"], p[alt_key], prefix)}</figure>'
        )
    grid = "\n".join(grid_lines)
    detail_html = detail if detail_link else ""
    return (
        f'<article class="room-section"><div class="room-header"><div class="room-number">{num}</div>'
        f'<div class="room-summary"><h3>{h3}{badge}</h3><p>{esc(loc["summary"])}</p>'
        f'<div class="room-tags">{tags}</div></div></div>\n'
        f'          <div class="room-photo-layout">\n'
        f'            <figure class="room-photo-main">{picture(main["src"], main[alt_key], prefix)}</figure>\n'
        f'            <div class="room-photo-grid">\n'
        f"{grid}\n"
        f"            </div>\n"
        f'          </div><div class="room-cta">{detail_html}'
        f'<a href="{esc(room["airbnb_url"])}" class="btn" target="_blank" rel="noopener"{airbnb_onclick(num)}>{cta}</a></div></article>'
    )


def rooms_section(rooms: list, lang: str) -> str:
    nums = [r["room_number"] for r in rooms]
    floors = {}
    for r in rooms:
        floors.setdefault(r["floor"], []).append(r["room_number"])
    if lang == "en":
        heading = f"Choose from Rooms {join_en(nums)}."
        floor_bits = []
        for fl in sorted(floors):
            ns = floors[fl]
            if len(ns) == 1:
                floor_bits.append(f"Room {ns[0]} is on the {ordinal(fl)} floor.")
            else:
                floor_bits.append(f"Rooms {join_en(ns)} are on the {ordinal(fl)} floor.")
        lead = "Each room has its own Airbnb page. " + " ".join(floor_bits)
    else:
        heading = "・".join(f"{n}号室" for n in nums) + "から選べます。"
        floor_bits = ["・".join(f"{n}号室" for n in floors[fl]) + f"は{fl}階" for fl in sorted(floors)]
        lead = "各部屋はAirbnbページから予約できます。" + "、".join(floor_bits) + "です。"
    articles = "\n".join(room_article(r, lang) for r in rooms)
    return (
        f'<section id="rooms" class="rooms"><div class="container"><div class="section-head">'
        f'<div class="section-kicker">Rooms</div><h2>{heading}</h2><p class="lead">{lead}</p></div>\n'
        f"{articles}\n"
        f"</div></section>"
    )


def booking_buttons(rooms: list, lang: str) -> str:
    parts = []
    for r in rooms:
        num = r["room_number"]
        label = f"View Room {num}" if lang == "en" else f"{num}号室を見る"
        parts.append(
            f'<a href="{esc(r["airbnb_url"])}" class="btn" target="_blank" rel="noopener"{airbnb_onclick(num)}>{label}</a>'
        )
    return "".join(parts)


def hero_room_tags(rooms: list, lang: str) -> str:
    nums = " / ".join(r["room_number"] for r in rooms)
    return f"<li>Rooms {nums}</li>" if lang == "en" else f"<li>{nums}号室</li>"


def legal_complete(legal: dict) -> bool:
    """法令表示の共通フィールドが全部そろっているか。"""
    if not legal.get("display"):
        return False
    required = ["facility_name", "operator_name", "license_type", "license_authority", "address"]
    return not any(not legal.get(k) for k in required)


def legal_notice(legal: dict, rooms: list, lang: str, room: dict = None) -> str:
    """フッター用の法令表示ブロック。

    - legal.display=true かつ共通フィールドが全部そろうまで空文字(=非表示)。
    - トップページ: 共通情報+license_number入力済みの部屋の許可番号一覧。
    - 個別ページ(room指定時): 共通情報+当該室の許可番号のみ。
      当該室の license_number が未入力の間は表示しない。
    """
    if not legal_complete(legal):
        return ""
    if room is not None and not room.get("license_number"):
        return ""
    if lang == "ja":
        common = (
            f"施設の名称: {esc(legal['facility_name'])} ／ 営業者: {esc(legal['operator_name'])} ／ "
            f"営業の種別: {esc(legal['license_type'])} ／ 許可: {esc(legal['license_authority'])} ／ "
            f"所在地: {esc(legal['address'])}"
        )
        if room is not None:
            nums = f"許可番号({esc(room['room_number'])}号室): {esc(room['license_number'])}"
        else:
            licensed = [r for r in rooms if r.get("license_number")]
            nums = " ／ ".join(
                f"{esc(r['room_number'])}号室: {esc(r['license_number'])}" for r in licensed
            )
            nums = f"許可番号 {nums}" if nums else ""
        title = "法令に基づく表示(旅館業法)"
    else:
        common = (
            f"Facility name: {esc(legal['facility_name'])} / Operator: {esc(legal['operator_name'])} / "
            f"License type: {esc(legal['license_type'])} / Licensed by: {esc(legal['license_authority'])} / "
            f"Address: {esc(legal['address'])}"
        )
        if room is not None:
            nums = f"License number (Room {esc(room['room_number'])}): {esc(room['license_number'])}"
        else:
            licensed = [r for r in rooms if r.get("license_number")]
            nums = " / ".join(
                f"Room {esc(r['room_number'])}: {esc(r['license_number'])}" for r in licensed
            )
            nums = f"License numbers: {nums}" if nums else ""
        title = "Legal information (Hotel Business Act)"
    nums_html = f"<p>{nums}</p>" if nums else ""
    return f'<div class="footer-legal"><p><strong>{title}</strong></p><p>{common}</p>{nums_html}</div>'


def render_page(template_name: str, lang: str, data: dict, rooms: list) -> str:
    tpl = (ROOT / "templates" / template_name).read_text(encoding="utf-8")
    seo = data["site"]["seo"][lang]
    out = tpl
    out = out.replace("{{META_DESCRIPTION}}", esc(seo["meta_description"]))
    out = out.replace("{{OG_DESCRIPTION}}", esc(seo["og_description"]))
    out = out.replace("{{HERO_ROOM_TAGS_LI}}", hero_room_tags(rooms, lang))
    out = out.replace("{{ROOMS_SECTION}}", rooms_section(rooms, lang))
    out = out.replace("{{BOOKING_BUTTONS}}", booking_buttons(rooms, lang))
    out = out.replace("{{LEGAL_NOTICE}}", legal_notice(data["legal"], rooms, lang))
    if "{{" in out:
        raise SystemExit(f"未解決のプレースホルダが残っています: {template_name}")
    return out


def other_room_buttons(room: dict, rooms: list, lang: str) -> str:
    parts = []
    for r in rooms:
        if r["room_number"] == room["room_number"]:
            continue
        num = r["room_number"]
        if lang == "en":
            parts.append(f'<a href="{num}.html" class="btn outline">Room {num}</a>')
        else:
            parts.append(f'<a href="{num}-ja.html" class="btn outline">{num}号室</a>')
    return "".join(parts)


def render_room_page(room: dict, lang: str, data: dict, rooms: list) -> str:
    base = data["site"]["base_url"]
    num = room["room_number"]
    en_url = f"{base}/rooms/{num}.html"
    ja_url = f"{base}/rooms/{num}-ja.html"
    template_name = "room-en.template.html" if lang == "en" else "room-ja.template.html"
    tpl = (ROOT / "templates" / template_name).read_text(encoding="utf-8")
    if lang == "en":
        title = f"Room {num} | Gold Town Kanamachi"
        crumb = f"Room {num}"
    else:
        title = f"{num}号室｜ゴールドタウン金町"
        crumb = f"{num}号室"
    out = tpl
    out = out.replace("{{TITLE}}", esc(title))
    out = out.replace("{{META_DESCRIPTION}}", esc(room[lang]["summary"]))
    out = out.replace("{{CANONICAL_URL}}", en_url if lang == "en" else ja_url)
    out = out.replace("{{EN_URL}}", en_url)
    out = out.replace("{{JA_URL}}", ja_url)
    out = out.replace("{{EN_FILE}}", f"{num}.html")
    out = out.replace("{{JA_FILE}}", f"{num}-ja.html")
    out = out.replace("{{OG_IMAGE}}", f"{base}/{room['photos']['main']['src']}")
    out = out.replace("{{BREADCRUMB_ROOM}}", crumb)
    out = out.replace("{{ROOM_ARTICLE}}", room_article(room, lang, prefix="../", detail_link=False))
    out = out.replace("{{OTHER_ROOM_BUTTONS}}", other_room_buttons(room, rooms, lang))
    out = out.replace("{{LEGAL_NOTICE}}", legal_notice(data["legal"], rooms, lang, room=room))
    if "{{" in out:
        raise SystemExit(f"未解決のプレースホルダが残っています: {template_name} ({num})")
    return out


def render_sitemap(data: dict, rooms: list) -> str:
    base = data["site"]["base_url"]
    lastmod = data["site"]["last_updated"]

    def url_entry(loc: str, prio: str, en_href: str, ja_href: str) -> str:
        return (
            "  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            "    <changefreq>weekly</changefreq>\n"
            f"    <priority>{prio}</priority>\n"
            f'    <xhtml:link rel="alternate" hreflang="en" href="{en_href}" />\n'
            f'    <xhtml:link rel="alternate" hreflang="ja" href="{ja_href}" />\n'
            f'    <xhtml:link rel="alternate" hreflang="x-default" href="{en_href}" />\n'
            "  </url>"
        )

    entries = [
        url_entry(f"{base}/", "1.0", f"{base}/", f"{base}/ja.html"),
        url_entry(f"{base}/ja.html", "0.9", f"{base}/", f"{base}/ja.html"),
    ]
    for r in rooms:
        num = r["room_number"]
        en_url = f"{base}/rooms/{num}.html"
        ja_url = f"{base}/rooms/{num}-ja.html"
        entries.append(url_entry(en_url, "0.8", en_url, ja_url))
        entries.append(url_entry(ja_url, "0.7", en_url, ja_url))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )


def main() -> int:
    data = json.loads((ROOT / "data" / "rooms.json").read_text(encoding="utf-8"))
    rooms = [r for r in data["rooms"] if r.get("active")]
    if not rooms:
        print("ERROR: activeな部屋が0件です。公開を中止します。", file=sys.stderr)
        return 1
    (ROOT / "index.html").write_text(render_page("index.template.html", "en", data, rooms), encoding="utf-8")
    (ROOT / "ja.html").write_text(render_page("ja.template.html", "ja", data, rooms), encoding="utf-8")
    (ROOT / "sitemap.xml").write_text(render_sitemap(data, rooms), encoding="utf-8")

    rooms_dir = ROOT / "rooms"
    rooms_dir.mkdir(exist_ok=True)
    expected = {}
    for r in rooms:
        expected[f"{r['room_number']}.html"] = render_room_page(r, "en", data, rooms)
        expected[f"{r['room_number']}-ja.html"] = render_room_page(r, "ja", data, rooms)
    for name, html in sorted(expected.items()):
        (rooms_dir / name).write_text(html, encoding="utf-8")
    removed = []
    for p in sorted(rooms_dir.glob("*.html")):
        if p.name not in expected:
            p.unlink()
            removed.append(p.name)
    msg = f"generated: index.html, ja.html, sitemap.xml, rooms/×{len(expected)} (rooms: {', '.join(r['room_number'] for r in rooms)})"
    if removed:
        msg += f" / 削除(非公開化): {', '.join('rooms/' + n for n in removed)}"
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
