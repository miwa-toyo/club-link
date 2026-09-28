from datetime import datetime
from typing import Optional

from clublink.extensions import db

SCHEDULE_KINDS = ("練習", "試合", "大会", "合宿", "遠征", "その他")
DEFAULT_TEAM_NAME = "全体"


class Team(db.Model):
    """チーム。Phase B時点ではクラブ作成時に自動生成される「全体」チームのみを使う。"""

    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False, index=True)
    club_year_id = db.Column(db.Integer, db.ForeignKey("club_years.id"), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)


class TeamMember(db.Model):
    """チームへの子供の所属。"""

    __tablename__ = "team_members"
    __table_args__ = (db.UniqueConstraint("team_id", "child_id", name="uq_team_member"),)

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False, index=True)
    child_id = db.Column(db.Integer, db.ForeignKey("children.id"), nullable=False, index=True)
    joined_at = db.Column(db.Date, default=datetime.utcnow, nullable=False)
    sort_index = db.Column(db.Integer, default=0, nullable=False)


class Schedule(db.Model):
    """予定（練習・試合・大会・合宿・遠征・その他）。"""

    __tablename__ = "schedules"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False)
    starts_at = db.Column(db.DateTime, nullable=False, index=True)
    place = db.Column(db.String(255), default="", nullable=False)
    needs_car = db.Column(db.Boolean, default=False, nullable=False)


class AbsenceReport(db.Model):
    """欠席連絡。行が存在する = その子供はその予定を欠席する。行が無ければ「参加」とみなす
    （既定は全員参加で、保護者は欠席のときだけ連絡する運用）。
    """

    __tablename__ = "absence_reports"
    __table_args__ = (
        db.UniqueConstraint("schedule_id", "child_id", name="uq_absence_schedule_child"),
    )

    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("schedules.id"), nullable=False, index=True)
    child_id = db.Column(db.Integer, db.ForeignKey("children.id"), nullable=False, index=True)
    reason = db.Column(db.String(255), default="", nullable=False)
    reported_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


def get_default_team(club_id: int) -> Optional[Team]:
    """Phase B時点で唯一のチーム（「全体」）を取得する。team_bp実装後は選択制にする。"""
    return Team.query.filter_by(club_id=club_id).order_by(Team.sort_order).first()
