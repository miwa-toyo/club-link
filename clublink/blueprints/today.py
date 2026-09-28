from datetime import date, datetime, time

from flask import Blueprint, render_template, session

from clublink.models import Announcement, Schedule
from clublink.security import require_login_guardian

today_bp = Blueprint("today", __name__)

UPCOMING_LIMIT = 5
RECENT_ANNOUNCEMENT_LIMIT = 5


@today_bp.route("/today")
@require_login_guardian
def today_dashboard():
    """予定（近い順）とお知らせ（新しい順）を、それぞれ分かりやすく分けて表示する。"""
    club_id = session["club_id"]
    today_start = datetime.combine(date.today(), time.min)

    schedules = (
        Schedule.query.filter(Schedule.club_id == club_id, Schedule.starts_at >= today_start)
        .order_by(Schedule.starts_at)
        .limit(UPCOMING_LIMIT)
        .all()
    )
    announcements = (
        Announcement.query.filter_by(club_id=club_id)
        .order_by(Announcement.posted_at.desc())
        .limit(RECENT_ANNOUNCEMENT_LIMIT)
        .all()
    )
    return render_template("today.html", schedules=schedules, announcements=announcements)
