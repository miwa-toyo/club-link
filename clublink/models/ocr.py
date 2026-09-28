from datetime import datetime

from clublink.extensions import db


class SchedulePhoto(db.Model):
    """予定表の写真とOCR抽出結果。schedule_id は未確定のアップロード直後は NULL を許容する
    （計画書の schedule_id 必須という定義から、アップロード先行フローに対応するための逸脱）。
    抽出結果はあくまで参考情報とし、管理者が手動で予定を作成・編集する運用とする（R1対策）。
    """

    __tablename__ = "schedule_photos"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False, index=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("schedules.id"), nullable=True, index=True)
    path = db.Column(db.String(255), nullable=False)
    ocr_text = db.Column(db.Text, default="", nullable=False)
    ocr_parsed = db.Column(db.Boolean, default=False, nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
