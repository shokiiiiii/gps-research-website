# GPS Co-location Research

研究成果を公開する [Quarto](https://quarto.org/) のWebサイトです。

## ローカルで確認する

```bash
pip install -r requirements.txt   # Quarto 本体（quarto-cli）が入ります
quarto preview                    # http://localhost:xxxx で自動リロード表示
```

## 週報を書く

```bash
python scripts/new_weekly.py      # 今週分の 05_weekly/posts/YYYY-MM-DD.qmd を作成
```

中身を書いて `main` に push すると、サイトの「週報」に追加されます。
ブラウザだけで書く場合は、GitHub 上で `05_weekly/posts/` に新しいファイルを作成してください（書式はサイトの週報ページに記載）。

## フォルダ構成

| パス | 内容 |
|---|---|
| `_quarto.yml` | サイト全体の設定（メニュー・テーマ） |
| `index.qmd` | トップページ |
| `01_workflow/` | 分析フロー |
| `02_methodology/` | 処理の詳細 |
| `03_source_code/` | 使用コード（.py / .ipynb） |
| `04_results/` | 分析結果 |
| `05_weekly/posts/` | 週報 |
| `_templates/` | 週報の雛形（サイトには出ません） |

## パスワード保護

`functions/_middleware.js` がサイト全体にログイン画面をかけます（Cloudflare Pages Functions）。

- Cloudflare Pages の環境変数 `SITE_PASSWORD` にパスワードを設定する（未設定だとサイトは表示されません）
- 一度ログインすると30日間有効。右上のアイコンからログアウトできます
- パスワードを変えると、全員のログインが解除されます
- `quarto preview` でのローカル確認ではパスワードはかかりません

## 公開（Cloudflare Pages）

| 設定項目 | 値 |
|---|---|
| Build command | `quarto render` |
| Build output directory | `_site` |

`requirements.txt` があるため、Cloudflare Pages がビルド前に Quarto を自動でインストールします。
