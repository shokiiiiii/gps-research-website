# 週報

研究の進捗を週ごとに記録します。新しい週報が上に表示されます。

??? tip "週報の書き方"
    **ローカルで書く場合**

    ```bash
    python scripts/new_weekly.py
    ```

    `docs/05_weekly/posts/<その週の月曜日>.md` が雛形から作成されるので、中身を書いて push します。

    **ブラウザだけで書く場合**

    GitHub で `docs/05_weekly/posts/` を開き「Add file → Create new file」から作成します。
    ファイル名は `2026-11-16.md` のように日付にし、先頭に次の行を入れてください。

    ```yaml
    ---
    date: 2026-11-16
    categories:
      - 週報
    ---
    ```

    既存の週報は、各ページ右上の :material-file-edit-outline: ボタンから直接編集できます。
