"""デモデータ投入スクリプト（Phase A: デモ用クラブ・オーナーのみ）。

実行方法:
    python scripts/seed_demo.py

/demo エンドポイントも同じデモアカウントを遅延生成するため、
本スクリプトは「起動前に確認したい」場合の明示的な事前投入用。
"""

from clublink import create_app
from clublink.blueprints.auth import DEMO_EMAIL
from clublink.models import User


def main() -> None:
    app = create_app()
    with app.app_context():
        if User.query.filter_by(email=DEMO_EMAIL).first() is not None:
            print(f"デモアカウントは既に存在します: {DEMO_EMAIL}")
            return

        from clublink.blueprints.auth import _create_demo_account

        _create_demo_account()
        print(f"デモアカウントを作成しました: {DEMO_EMAIL}")


if __name__ == "__main__":
    main()
