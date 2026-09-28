import pytest

from clublink import create_app
from clublink.config import Config
from clublink.extensions import db


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = "/tmp/clublink_test_uploads"


@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.test_client() as test_client:
        yield test_client
    with app.app_context():
        db.drop_all()


def register_club(
    client,
    club_name: str = "テストクラブ",
    display_name: str = "山田太郎",
    email: str = "yamada@example.com",
    password: str = "password123",
) -> None:
    """新規クラブを作成し、そのオーナー（重要管理者）としてログイン済みにする。

    デモ専用アカウントを廃止したため、各テストはこのヘルパーで
    実際の登録フローと同じ経路からログイン状態を作る。
    """
    client.post(
        "/register",
        data={
            "club_name": club_name,
            "display_name": display_name,
            "email": email,
            "password": password,
        },
    )


def seed_sample_data(client) -> None:
    """お知らせ・ルール・FAQ・予定・子供のサンプルを現在ログイン中のクラブに投入する。"""
    client.post("/admin/sample-data")


def get_invite_code(app, club_name: str = "テストクラブ") -> str:
    """テスト内でクラブの招待コードを取得する（招待経由の一般保護者を作るときに使う）。"""
    with app.app_context():
        from clublink.models import Club

        return Club.query.filter_by(name=club_name).first().invite_code


def join_as_general_guardian(
    client,
    app,
    club_name: str = "テストクラブ",
    display_name: str = "一般 花子",
    email: str = "hanako@example.com",
    password: str = "password123",
) -> None:
    """招待コード経由で、管理者権限を持たない一般保護者として参加する。"""
    invite_code = get_invite_code(app, club_name)
    client.post(
        "/invite",
        data={
            "invite_code": invite_code,
            "display_name": display_name,
            "email": email,
            "password": password,
        },
    )
