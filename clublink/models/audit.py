from datetime import datetime

from clublink.extensions import db


class AuditLog(db.Model):
    """重要操作の監査ログ。会計・管理者・ルール変更などで書き込む。"""

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50), nullable=False)
    target_id = db.Column(db.Integer, nullable=True)
    before = db.Column(db.Text, nullable=True)
    after = db.Column(db.Text, nullable=True)
    at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
