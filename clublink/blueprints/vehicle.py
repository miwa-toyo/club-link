from flask import Blueprint, abort, redirect, render_template, session, url_for

from clublink.blueprints.schedule import get_schedule_or_404
from clublink.context import current_guardian, is_editor
from clublink.extensions import db
from clublink.forms import ParkingLotForm, VehicleAssignmentForm
from clublink.models import Guardian, ParkingLot, VehicleAssignment
from clublink.security import require_admin_level, require_login_guardian

vehicle_bp = Blueprint("vehicle", __name__)


@vehicle_bp.route("/schedules/<int:schedule_id>/vehicle", methods=["GET", "POST"])
@require_login_guardian
def vehicle_assign(schedule_id: int):
    """車出しの自己申告制登録。送迎可否は本人のマイページ設定（Guardian.can_drive）に基づく。"""
    schedule = get_schedule_or_404(schedule_id)
    guardian = current_guardian()
    form = VehicleAssignmentForm()

    if form.validate_on_submit():
        if not guardian.can_drive:
            abort(403)
        assignment = VehicleAssignment.query.filter_by(
            schedule_id=schedule.id, guardian_id=guardian.id, direction=form.direction.data
        ).first() or VehicleAssignment(
            schedule_id=schedule.id, guardian_id=guardian.id, direction=form.direction.data
        )
        assignment.comment = form.comment.data or ""
        db.session.add(assignment)
        db.session.commit()
        return redirect(url_for("vehicle.vehicle_assign", schedule_id=schedule.id))

    assignments = (
        db.session.query(VehicleAssignment, Guardian)
        .join(Guardian, VehicleAssignment.guardian_id == Guardian.id)
        .filter(VehicleAssignment.schedule_id == schedule.id)
        .all()
    )
    return render_template(
        "vehicle_assign.html",
        schedule=schedule,
        assignments=assignments,
        form=form,
        can_drive=guardian.can_drive,
        current_guardian_id=guardian.id,
    )


@vehicle_bp.route(
    "/schedules/<int:schedule_id>/vehicle/<int:assignment_id>/delete", methods=["POST"]
)
@require_login_guardian
def vehicle_unassign(schedule_id: int, assignment_id: int):
    """自分の申し出のみ取り消せる（管理者は「編集」権限があれば誰の分でも取り消せる）。"""
    schedule = get_schedule_or_404(schedule_id)
    assignment = VehicleAssignment.query.get_or_404(assignment_id)
    if assignment.schedule_id != schedule.id:
        abort(404)

    guardian = current_guardian()
    if assignment.guardian_id != guardian.id and not is_editor():
        abort(403)

    db.session.delete(assignment)
    db.session.commit()
    return redirect(url_for("vehicle.vehicle_assign", schedule_id=schedule.id))


@vehicle_bp.route("/parking", methods=["GET", "POST"])
@require_admin_level("編集")
def parking_admin():
    form = ParkingLotForm()
    if form.validate_on_submit():
        db.session.add(
            ParkingLot(
                club_id=session["club_id"],
                name=form.name.data,
                address=form.address.data or "",
                capacity=form.capacity.data or 0,
                memo=form.memo.data or "",
            )
        )
        db.session.commit()
        return redirect(url_for("vehicle.parking_admin"))

    lots = ParkingLot.query.filter_by(club_id=session["club_id"]).all()
    return render_template("parking_admin.html", lots=lots, form=form)


@vehicle_bp.route("/parking/<int:lot_id>/delete", methods=["POST"])
@require_admin_level("編集")
def parking_delete(lot_id: int):
    lot = ParkingLot.query.get_or_404(lot_id)
    if lot.club_id != session["club_id"]:
        abort(404)
    db.session.delete(lot)
    db.session.commit()
    return redirect(url_for("vehicle.parking_admin"))
