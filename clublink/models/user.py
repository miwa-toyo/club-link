from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from clublink.extensions import db

ADMIN_LEVELS = ("閲覧", "編集", "重要管理")


class User(UserMixin, db.Model):
    """ログインアカウント。クラブに依存しないグローバルな認証単位。"""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)


class Guardian(db.Model):
    """クラブ内の保護者メンバーシップ。Phase A では 1 ユーザー = 1 クラブとして運用する。"""

    __tablename__ = "guardians"
    __table_args__ = (db.UniqueConstraint("club_id", "user_id", name="uq_guardian_club_user"),)

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    display_name = db.Column(db.String(100), nullable=False)
    can_drive = db.Column(db.Boolean, default=False, nullable=False)
    vehicle_seats = db.Column(db.Integer, default=0, nullable=False)

    children = db.relationship(
        "Child", secondary="guardian_children", back_populates="guardians"
    )


class AdminRole(db.Model):
    """クラブ内の管理者権限。level は ADMIN_LEVELS のいずれか。"""

    __tablename__ = "admin_roles"
    __table_args__ = (db.UniqueConstraint("club_id", "user_id", name="uq_admin_club_user"),)

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)
    level = db.Column(db.String(20), nullable=False)
