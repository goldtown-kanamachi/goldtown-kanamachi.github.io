#!/usr/bin/env python3
"""rooms.json から index.html / ja.html / sitemap.xml を生成する。

使い方:  python3 scripts/generate.py
入力:    data/rooms.json, templates/*.template.html
出力:    index.html, ja.html, sitemap.xml (リポジトリルート)

設計原則:
- 依存ライブラリなし(Python 3 標準ライブラリのみ)。
- 出力は決定的(同じ rooms.json からは常に同じバイト列)。
- active が false の部屋はページ・予約ボタンから除外される。
- legal.display が false または未設定の間、法令表示ブロックは出力しない。
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


def room_article(room: dict, lang: str) -> str:
    num = room["room_number"]
    loc = room[lang]
    if lang == "en":
        h3 = f"Room {num}"
        badge = ' <span class="section-kicker">New</span>' if room["is_new"] else ""
        cta = f"View Room {num} on Airbnb"
        alt_key = "alt_en"
    else:
        h3 = f"{num}号室"
        badge = ' <span class="section-kicker">新規開業</span>' if room["is_new"] else ""
        cta = f"Airbnbで{num}号室を見る"
        alt_key = "alt_ja"
    tags = "".join(f"<span>{esc(t)}</span>" for t in loc["tags"])
    main = room["photos"]["main"]
    grid_lines = []
    for i, p in enumerate(room["photos"]["grid"]):
        prefix = "              " if i == 0 else ""
        grid_lines.append(
            f'{prefix}<figure><img src="{esc(p["src"])}" alt="{esc(p[alt_key])}" loading="lazy"></figure>'
        )
    grid = "\n".join(grid_lines)
    return (
        f'<article class="room-section"><div class="room-header"><div class="room-number">{num}</div>'
        f'<div class="room-summary"><h3>{h3}{badge}</h3><p>{esc(loc["summary"])}</p>'
        f'<div class="room-tags">{tags}</div></div></div>\n'
        f'          <div class="room-photo-layout">\n'
        f'            <figure class="room-photo-main"><img src="{esc(main["src"])}" alt="{esc(main[alt_key])}" loading="lazy"></figure>\n'
        f'            <div class="room-photo-grid">\n'
        f"{grid}\n"
        f"            </div>\n"
        f'          </div><div class="room-cta"><a href="{esc(room["airbnb_url"])}" class="btn" target="_blank" rel="noopener">{cta}</a></div></article>'
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
        label = f"View Room {r['room_number']}" if lang == "en" else f"{r['room_number']}号室を見る"
        parts.append(
            f'<a href="{esc(r["airbnb_url"])}" class="btn" target="_blank" rel="noopener">{label}</a>'
        )
    return "".join(parts)


def hero_room_tags(rooms: list, lang: str) -> str:
    nums = " / ".join(r["room_number"] for r in rooms)
    return f"<li>Rooms {nums}</li>" if lang == "en" else f"<li>{nums}号室</li>"


def legal_notice(legal: dict, rooms: list, lang: str) -> str:
    """法令表示ブロック。display が true かつ全フィールドが揃うまで空文字を返す。"""
    if not legal.get("display"):
        return ""
    required = ["facility_name", "operator_name", "license_type", "license_authority", "address"]
    if any(not legal.get(k) for k in required):
        return ""
    licensed = [r for r in rooms if r.get("license_number")]
    if lang == "ja":
        lines = "".join(
            f"<li>{esc(r['room_number'])}号室: {esc(r['license_number'])}</li>" for r in licensed
        )
        return (
            '<section id="legal" class="legal-notice"><div class="container">'
            f"<h2>法令に基づく表示</h2>"
            f"<p>施設の名称: {esc(legal['facility_name'])} / 営業者: {esc(legal['operator_name'])} / "
            f"営業の種別: {esc(legal['license_type'])} / 許可: {esc(legal['license_authority'])} / "
            f"所在地: {esc(legal['address'])}</p>"
            f"<ul>{lines}</ul>"
            "</div></section>"
        )
    lines = "".join(
        f"<li>Room {esc(r['room_number'])}: {esc(r['license_number'])}</li>" for r in licensed
    )
    return (
        '<section id="legal" class="legal-notice"><div class="container">'
        f"<h2>Legal information</h2>"
        f"<p>Facility name: {esc(legal['facility_name'])} / Operator: {esc(legal['operator_name'])} / "
        f"License type: {esc(legal['license_type'])} / Licensed by: {esc(legal['license_authority'])} / "
        f"Address: {esc(legal['address'])}</p>"
        f"<ul>{lines}</ul>"
        "</div></section>"
    )


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


def render_sitemap(data: dict) -> str:
    base = data["site"]["base_url"]
    lastmod = data["site"]["last_updated"]
    pages = [(f"{base}/", "1.0"), (f"{base}/ja.html", "0.9")]
    alt = (
        f'    <xhtml:link rel="alternate" hreflang="en" href="{base}/" />\n'
        f'    <xhtml:link rel="alternate" hreflang="ja" href="{base}/ja.html" />\n'
        f'    <xhtml:link rel="alternate" hreflang="x-default" href="{base}/" />\n'
    )
    entries = []
    for loc, prio in pages:
        entries.append(
            "  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            "    <changefreq>weekly</changefreq>\n"
            f"    <priority>{prio}</priority>\n"
            f"{alt}"
            "  </url>"
        )
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
    (ROOT / "sitemap.xml").write_text(render_sitemap(data), encoding="utf-8")
    print(f"generated: index.html, ja.html, sitemap.xml (rooms: {', '.join(r['room_number'] for r in rooms)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
