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

## 公開（Cloudflare Pages）

| 設定項目 | 値 |
|---|---|
| Build command | `quarto render` |
| Build output directory | `_site` |

`requirements.txt` があるため、Cloudflare Pages がビルド前に Quarto を自動でインストールします。
