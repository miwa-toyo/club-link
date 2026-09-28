import secrets
from datetime import datetime

from clublink.extensions import db

INVITE_CODE_BYTES = 4  # token_hex(4) -> 8桁の16進文字列


def generate_invite_code() -> str:
    """クラブ招待コードを生成する。衝突確認は呼び出し側の一意制約に委ねる。"""
    return secrets.token_hex(INVITE_CODE_BYTES)


class Club(db.Model):
    """クラブ（テナント）。全主要テーブルはこの club_id で分離される。"""

    __tablename__ = "clubs"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    invite_code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ClubSetting(db.Model):
    """クラブごとの設定。「お問い合わせ窓口」の連絡先情報を保持する。"""

    __tablename__ = "club_settings"

    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), primary_key=True)
    contact_info = db.Column(db.Text, default="", nullable=False)


class ClubYear(db.Model):
    """年度。is_current が True の行が常に1件になるよう運用（年度更新機能）で担保する。"""

    __tablename__ = "club_years"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False, index=True)
    name = db.Column(db.String(20), nullable=False)
    is_current = db.Column(db.Boolean, default=True, nullable=False)
