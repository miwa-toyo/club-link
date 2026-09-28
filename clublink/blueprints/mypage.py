from datetime import datetime, timedelta

from flask import Blueprint, abort, redirect, render_template, request, session, url_for

from clublink.context import current_guardian
from clublink.extensions import db
from clublink.forms import AbsenceReportForm, ChildForm, VehicleForm
from clublink.models import AbsenceReport, Child, Schedule
from clublink.security import require_login_guardian

mypage_bp = Blueprint("mypage", __name__, url_prefix="/me")

# 欠席連絡の対象は「件数」ではなく「今後60日以内」で区切る。
# 予定が多い時期に10件しか連絡できない、といった不便を避けるため。
ABSENCE_REPORT_WINDOW_DAYS = 60


@mypage_bp.route("")
@require_login_guardian
def mypage():
    return render_template("mypage.html", guardian=current_guardian())


@mypage_bp.route("/vehicle", methods=["GET", "POST"])
@require_login_guardian
def vehicle_edit():
    """保護者自身の送迎可否・乗車可能人数を編集する。"""
    guardian = current_guardian()
    form = VehicleForm(obj=guardian)
    if form.validate_on_submit():
        guardian.can_drive = form.can_drive.data
        guardian.vehicle_seats = form.vehicle_seats.data
        db.session.commit()
        return redirect(url_for("mypage.mypage"))
    return render_template("vehicle_edit.html", form=form)


@mypage_bp.route("/family", methods=["GET", "POST"])
@require_login_guardian
def family_edit():
    """子供一覧の表示 + 新規追加。"""
    guardian = current_guardian()
    form = ChildForm()
    if form.validate_on_submit():
        child = Child(
            club_id=guardian.club_id,
            family_name=form.family_name.data,
            court_name=form.court_name.data,
            birth_date=form.birth_date.data,
            gender=form.gender.data,
            allergy=form.allergy.data or "",
            status=form.status.data,
        )
        child.guardians.append(guardian)
        db.session.add(child)
        db.session.commit()
        return redirect(url_for("mypage.family_edit"))
    return render_template("family_edit.html", guardian=guardian, form=form)


@mypage_bp.route("/family/<int:child_id>", methods=["GET", "POST"])
@require_login_guardian
def child_edit(child_id: int):
    child = _get_own_child_or_404(child_id)
    form = ChildForm(obj=child)
    if form.validate_on_submit():
        child.family_name = form.family_name.data
        child.court_name = form.court_name.data
        child.birth_date = form.birth_date.data
        child.gender = form.gender.data
        child.allergy = form.allergy.data or ""
        child.status = form.status.data
        db.session.commit()
        return redirect(url_for("mypage.family_edit"))
    return render_template("child_edit.html", form=form, child=child)


@mypage_bp.route("/absences")
@require_login_guardian
def absence_report():
    """欠席連絡の一覧。予定は基本「全員参加」とみなし、欠席するときだけ日付ごとに連絡する。"""
    guardian = current_guardian()
    window_end = datetime.utcnow() + timedelta(days=ABSENCE_REPORT_WINDOW_DAYS)
    schedules = (
        Schedule.query.filter(
            Schedule.club_id == session["club_id"],
            Schedule.starts_at >= datetime.utcnow(),
            Schedule.starts_at <= window_end,
        )
        .order_by(Schedule.starts_at)
        .all()
    )
    existing = {
        (report.schedule_id, report.child_id): report
        for report in AbsenceReport.query.filter(
            AbsenceReport.schedule_id.in_([s.id for s in schedules])
        ).all()
    }
    return render_template(
        "absence_report.html",
        schedules=schedules,
        children=guardian.children,
        existing=existing,
        form=AbsenceReportForm(),
    )


@mypage_bp.route("/absences/<int:schedule_id>", methods=["POST"])
@require_login_guardian
def absence_report_save(schedule_id: int):
    """特定の1つの予定（日付）だけの欠席連絡を保存する。他の日付には影響しない。"""
    guardian = current_guardian()
    form = AbsenceReportForm()
    if not form.validate_on_submit():
        abort(400)

    for child in guardian.children:
        _apply_absence(schedule_id, child.id, request.form)
    db.session.commit()
    return redirect(url_for("mypage.absence_report"))


def _apply_absence(schedule_id: int, child_id: int, form_data) -> None:
    """チェックが入っていれば欠席連絡を登録・更新し、外れていれば連絡を取り消す（＝参加扱いに戻す）。"""
    field_prefix = f"{schedule_id}_{child_id}"
    is_absent = form_data.get(f"absent_{field_prefix}") == "on"
    report = AbsenceReport.query.filter_by(schedule_id=schedule_id, child_id=child_id).first()

    if not is_absent:
        if report is not None:
            db.session.delete(report)
        return

    if report is None:
        report = AbsenceReport(schedule_id=schedule_id, child_id=child_id)
        db.session.add(report)
    report.reason = form_data.get(f"reason_{field_prefix}", "").strip()
    report.reported_at = datetime.utcnow()


def _get_own_child_or_404(child_id: int) -> Child:
    guardian = current_guardian()
    child = Child.query.get_or_404(child_id)
    if child.club_id != guardian.club_id or guardian not in child.guardians:
        abort(404)
    return child
