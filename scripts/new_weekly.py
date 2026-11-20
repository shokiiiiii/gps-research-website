"""週報の雛形を作成する。

使い方:
    python scripts/new_weekly.py              # 今週（月曜はじまり）
    python scripts/new_weekly.py 2026-11-16   # 指定日を含む週

05_weekly/posts/YYYY-MM-DD.qmd が作成される（日付は週の月曜日）。
"""
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "_templates" / "weekly_report.qmd"
POSTS_DIR = ROOT / "05_weekly" / "posts"


def main() -> None:
    day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    monday = day - timedelta(days=day.weekday())
    friday = monday + timedelta(days=4)

    out = POSTS_DIR / f"{monday.isoformat()}.qmd"
    if out.exists():
        sys.exit(f"既に存在します: {out.relative_to(ROOT)}")

    text = TEMPLATE.read_text(encoding="utf-8").format(
        date=monday.isoformat(),
        start=monday.strftime("%Y/%m/%d"),
        end=friday.strftime("%m/%d"),
    )
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"作成しました: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
