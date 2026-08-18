# 客室データ運用ガイド(rooms.json)

このサイトの客室情報は `data/rooms.json` の1ファイルで管理します。
HTMLを直接編集しないでください(次回の生成で上書きされます)。

## 基本の流れ

1. `data/rooms.json` を編集する
2. 写真を追加・差し替えた場合は `python3 scripts/convert_images.py` でWebPを生成
3. `python3 scripts/generate.py` で `index.html` / `ja.html` / `sitemap.xml` /
   `rooms/`(客室個別ページ・日英)を再生成
4. `python3 scripts/validate.py` で検査(入力漏れ・リンク切れ・整合をエラーで教えてくれます)
5. 変更をブランチにコミットしてPRを作成 → CI(check)が自動検査 → 確認してマージ

`site.last_updated` は内容を変えたときに今日の日付(YYYY-MM-DD)へ更新してください(sitemapのlastmodに反映されます)。

## よくある操作

### 部屋を予約停止にする
その部屋の `"active": true` を `false` にして `generate.py` を再実行するだけです。
日英ページの客室一覧・予約ボタン・フロア案内文に加え、その部屋の個別ページ
(`rooms/<番号>.html` / `rooms/<番号>-ja.html`)と sitemap のURLも自動で消えます
(個別ページのファイルは generate.py が自動削除します。削除もコミットしてください)。

### 部屋を追加する
`rooms` 配列に既存の部屋をコピーして書き換えます。必須項目:
`room_number`(数字のみ)、`active`、`is_new`(Newバッジ)、`floor`、
`airbnb_url`(https://www.airbnb.jp/rooms/数字)、`en`/`ja` の `summary` と `tags`、
`photos`(main 1枚+grid 1枚以上。画像は `images/` に置き、`alt_en`/`alt_ja` を必ず入れる)。
見出し・フロア案内・予約ボタン・ヒーローの部屋番号表示は自動で更新されます。

### 写真を差し替える
画像ファイルを `images/` に追加し、`photos` の `src` と alt を書き換えます。
存在しないファイル名を書くと validate.py が止めてくれます。

追加後に `python3 scripts/convert_images.py` を実行すると、軽量なWebP版
(元ファイル名 + `.webp`)が作られ、ページは自動的にWebP優先+従来形式
フォールバックの `<picture>` で配信されます。原本のjpg/pngは上書きされません。
変換済みの画像は `data/image_cache.json` に記録され、再実行しても再変換されません。
WebPが無い画像も表示はされます(従来どおり `<img>` のみになるだけ)。

### 法令表示(旅館業許可)を出す
掲載の裁定が出るまで `legal.display` は `false` のままにしてください。
掲載する場合は、許可証の記載どおりに:

- `legal.facility_name` / `operator_name` / `license_type` / `license_authority` / `address` を入力
- 各部屋の `license_number` に許可番号を入力
- `legal.display` を `true` に変更

これだけで日英両ページと各個別ページのフッターに法令表示ブロックが自動で入ります
(個別ページには当該室の許可番号のみ表示)。
フィールドが1つでも未入力のうちは `display: true` にしてもCIが止めます(誤掲載防止)。

## してはいけないこと

- **このリポジトリは全世界に公開されています。** キーボックスの暗証番号、ゲスト情報、
  認証情報(パスワード・APIキー等)、内部運用メモは絶対にコミットしないでください。
  CIのgitleaksスキャンが検出した場合、マージできなくなります。
- `index.html` / `ja.html` / `sitemap.xml` の直接編集(rooms.jsonと不一致になりCIが止まります)。
  ページの文面そのもの(客室以外のセクション)を変えたいときは `templates/` を編集してください。

## ファイル構成

| パス | 役割 |
|---|---|
| `data/rooms.json` | 客室データの正本(これだけ編集すればよい) |
| `data/image_cache.json` | WebP変換のキャッシュ(自動生成・手編集不要) |
| `templates/index.template.html` | 英語トップページの雛形(客室部分はプレースホルダ) |
| `templates/ja.template.html` | 日本語トップページの雛形 |
| `templates/room-en.template.html` | 客室個別ページ(英語)の雛形 |
| `templates/room-ja.template.html` | 客室個別ページ(日本語)の雛形 |
| `rooms/` | 客室個別ページ(自動生成・直接編集しない) |
| `scripts/validate.py` | 入力漏れ・誤り・個別ページ/リンク/hreflang整合の検査 |
| `scripts/generate.py` | トップ・個別ページ・sitemapの生成 |
| `scripts/convert_images.py` | 画像のWebP変換(原本は保持・キャッシュ付き) |
| `.github/workflows/check.yml` | PR/push時の自動検査(秘密情報・検査・生成一致) |
