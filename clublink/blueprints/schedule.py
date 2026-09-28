from flask import Blueprint, abort, redirect, render_template, session, url_for

from clublink.context import is_editor
from clublink.extensions import db
from clublink.forms import ScheduleForm
from clublink.models import AbsenceReport, Child, Schedule, get_default_team
from clublink.security import require_admin_level, require_login_guardian

schedule_bp = Blueprint("schedule", __name__, url_prefix="/schedules")


@schedule_bp.route("")
@require_login_guardian
def schedule_list():
    """年間予定。年月ごとにグループ化して表示する。"""
    schedules = (
        Schedule.query.filter_by(club_id=session["club_id"])
        .order_by(Schedule.starts_at)
        .all()
    )
    return render_template("schedule_list.html", schedules_by_month=_group_by_month(schedules))


def _group_by_month(schedules: list) -> list:
    """予定を「YYYY年M月」ごとにまとめる（古い月から順）。"""
    grouped: dict = {}
    order: list = []
    for schedule in schedules:
        label = f"{schedule.starts_at.year}年{schedule.starts_at.month}月"
        if label not in grouped:
            grouped[label] = []
            order.append(label)
        grouped[label].append(schedule)
    return [(label, grouped[label]) for label in order]


@schedule_bp.route("/new", methods=["GET", "POST"])
@require_admin_level("編集")
def schedule_new():
    """予定の新規作成（管理者限定）。Phase B時点ではクラブ唯一のチームに紐づける。"""
    team = get_default_team(session["club_id"])
    if team is None:
        abort(500)

    form = ScheduleForm()
    if form.validate_on_submit():
        schedule = Schedule(
            club_id=session["club_id"],
            team_id=team.id,
            kind=form.kind.data,
            starts_at=form.starts_at.data,
            place=form.place.data or "",
            needs_car=form.needs_car.data,
        )
        db.session.add(schedule)
        db.session.commit()
        return redirect(url_for("schedule.schedule_list"))
    return render_template("schedule_new.html", form=form)


@schedule_bp.route("/<int:schedule_id>")
@require_login_guardian
def schedule_detail(schedule_id: int):
    """予定の詳細。出欠は「基本は全員参加、欠席のみマイページから連絡」という運用のため、
    ここでは管理者向けに欠席者一覧だけを表示する（連絡自体はマイページで行う）。
    """
    schedule = get_schedule_or_404(schedule_id)
    absences = []
    if is_editor():
        absences = (
            db.session.query(AbsenceReport, Child)
            .join(Child, AbsenceReport.child_id == Child.id)
            .filter(AbsenceReport.schedule_id == schedule.id)
            .all()
        )
    return render_template(
        "schedule_detail.html", schedule=schedule, absences=absences, can_edit=is_editor()
    )


def get_schedule_or_404(schedule_id: int) -> Schedule:
    """他Blueprint（vehicle等）からも参照する共有ヘルパー。"""
    schedule = Schedule.query.get_or_404(schedule_id)
    if schedule.club_id != session["club_id"]:
        abort(404)
    return schedule
