import secrets

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user

from clublink.audit import log_action
from clublink.context import can_start_preview
from clublink.extensions import db
from clublink.forms import AdminRoleForm, ClubYearForm, PlanChangeForm
from clublink.models import (
    AbsenceReport,
    AdminRole,
    AuditLog,
    Child,
    Club,
    ClubYear,
    Guardian,
    Plan,
    PlanFeature,
    Schedule,
    Subscription,
    User,
)
from clublink.models.family import CHILD_STATUSES
from clublink.sample_data import delete_sample_content, seed_sample_content
from clublink.security import require_admin_level, require_login_guardian

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

IMPORTANT_ADMIN_LEVEL = "重要管理"
AUDIT_LOG_LIMIT = 100
RECENT_ABSENCE_LIMIT = 5


@admin_bp.route("")
@require_admin_level("閲覧")
def admin_home():
    club_id = session["club_id"]
    club = Club.query.get_or_404(club_id)
    admin_count = AdminRole.query.filter_by(club_id=club_id).count()
    guardian_count = Guardian.query.filter_by(club_id=club_id).count()
    my_role = AdminRole.query.filter_by(club_id=club_id, user_id=current_user.id).first()
    recent_absences = _recent_absences(club_id)
    return render_template(
        "admin_home.html",
        club=club,
        admin_count=admin_count,
        guardian_count=guardian_count,
        my_role=my_role,
        recent_absences=recent_absences,
    )


def _recent_absences(club_id: int):
    """直近に届いた欠席連絡を、通知代わりに新しい順で返す。"""
    return (
        db.session.query(AbsenceReport, Child, Schedule)
        .join(Child, AbsenceReport.child_id == Child.id)
        .join(Schedule, AbsenceReport.schedule_id == Schedule.id)
        .filter(Schedule.club_id == club_id)
        .order_by(AbsenceReport.reported_at.desc())
        .limit(RECENT_ABSENCE_LIMIT)
        .all()
    )


@admin_bp.route("/sample-data", methods=["POST"])
@require_admin_level("編集")
def seed_sample_data():
    """動作確認用のサンプルデータ（お知らせ・ルール・FAQ・予定・子供）をこのクラブに投入する。"""
    club = Club.query.get_or_404(session["club_id"])
    seed_sample_content(club, current_user)
    db.session.commit()
    flash("サンプルデータを投入しました。", "success")
    return redirect(url_for("admin.admin_home"))


@admin_bp.route("/sample-data/delete", methods=["POST"])
@require_admin_level("編集")
def delete_sample_data():
    """投入済みのサンプルデータ（お知らせ・ルール・FAQ・予定・子供）をこのクラブから削除する。"""
    delete_sample_content(session["club_id"])
    db.session.commit()
    flash("サンプルデータを削除しました。", "success")
    return redirect(url_for("admin.admin_home"))


@admin_bp.route("/preview/start", methods=["POST"])
@require_admin_level("編集")
def preview_start():
    """一般保護者としてのプレビューを開始する。以降、管理者専用の項目は一切見えなくなる。"""
    session["preview_mode"] = True
    return redirect(url_for("today.today_dashboard"))


@admin_bp.route("/preview/stop", methods=["POST"])
@require_login_guardian
def preview_stop():
    """プレビューを終了し、元の権限に戻る。プレビュー中でも実行できるようrequire_admin_levelは使わない。"""
    session.pop("preview_mode", None)
    if can_start_preview():
        return redirect(url_for("admin.admin_home"))
    return redirect(url_for("today.today_dashboard"))


@admin_bp.route("/admins", methods=["GET", "POST"])
@require_admin_level(IMPORTANT_ADMIN_LEVEL)
def admin_add():
    """管理者権限の付与・変更・解除。重要管理者が0人になる操作は422で拒否する（R6対策）。"""
    club_id = session["club_id"]
    form = AdminRoleForm()

    if request.method == "POST":
        guardian_id = request.form.get("guardian_id", type=int)
        if request.form.get("action") == "remove":
            _remove_admin_role(club_id, guardian_id)
            return redirect(url_for("admin.admin_add"))
        if form.validate_on_submit():
            _upsert_admin_role(club_id, form.guardian_id.data, form.name.data, form.level.data)
            return redirect(url_for("admin.admin_add"))

    keyword = request.args.get("q", "").strip()
    query = Guardian.query.filter_by(club_id=club_id)
    if keyword:
        query = query.filter(Guardian.display_name.like(f"%{keyword}%"))
    guardians = query.order_by(Guardian.display_name).all()
    roles = {role.user_id: role for role in AdminRole.query.filter_by(club_id=club_id).all()}
    return render_template(
        "admin_list.html", guardians=guardians, roles=roles, form=form, keyword=keyword
    )


@admin_bp.route("/admins/<int:guardian_id>/reset-password", methods=["POST"])
@require_admin_level(IMPORTANT_ADMIN_LEVEL)
def admin_reset_password(guardian_id: int):
    """保護者のパスワードを管理者がその場で再設定する。新しい仮パスワードは一度だけ画面に表示されるため、
    その場でメモして本人に伝える（メール送信の仕組みは無いため）。
    """
    club_id = session["club_id"]
    guardian = Guardian.query.get_or_404(guardian_id)
    if guardian.club_id != club_id:
        abort(404)

    user = User.query.get_or_404(guardian.user_id)
    new_password = secrets.token_urlsafe(6)
    user.set_password(new_password)
    db.session.add(user)
    log_action(club_id, current_user.id, "password_reset", "Guardian", guardian.id)
    db.session.commit()

    flash(
        f"{guardian.display_name} さんの新しいパスワード：{new_password}"
        "（この画面にのみ一度だけ表示されます。必ずメモしてご本人にお伝えください）",
        "success",
    )
    return redirect(url_for("admin.admin_add"))


@admin_bp.route("/year", methods=["GET", "POST"])
@require_admin_level(IMPORTANT_ADMIN_LEVEL)
def year_update():
    """年度更新。現行年度を is_current=False にし、新しい年度を is_current=True で作成する。"""
    club_id = session["club_id"]
    form = ClubYearForm()

    if form.validate_on_submit():
        current_year = ClubYear.query.filter_by(club_id=club_id, is_current=True).first()
        if current_year is not None:
            current_year.is_current = False
            db.session.add(current_year)
        db.session.add(ClubYear(club_id=club_id, name=form.name.data, is_current=True))
        log_action(club_id, current_user.id, "year_updated", "ClubYear")
        db.session.commit()
        return redirect(url_for("admin.year_update"))

    years = ClubYear.query.filter_by(club_id=club_id).order_by(ClubYear.id.desc()).all()
    children = Child.query.filter_by(club_id=club_id).order_by(Child.family_name).all()
    return render_template(
        "year_update.html",
        years=years,
        form=form,
        children=children,
        alumni_by_year=_group_alumni_by_year(children, years),
    )


@admin_bp.route("/year/members", methods=["POST"])
@require_admin_level(IMPORTANT_ADMIN_LEVEL)
def year_member_bulk_update():
    """OB/OG管理：子供の在籍状態（在籍/卒団/退部）と、卒団・退部した年度を一括更新する。"""
    club_id = session["club_id"]
    for child in Child.query.filter_by(club_id=club_id).all():
        status = request.form.get(f"status_{child.id}")
        if status not in CHILD_STATUSES:
            continue
        child.status = status
        if status == "active":
            child.left_club_year_id = None
        else:
            child.left_club_year_id = request.form.get(f"left_year_{child.id}", type=int)
        db.session.add(child)
    db.session.commit()
    return redirect(url_for("admin.year_update"))


def _group_alumni_by_year(children, years) -> list:
    """卒団・退部した子供を、卒団/退部した年度ごとにまとめる（年度作成順）。"""
    year_names = {year.id: year.name for year in years}
    grouped: dict = {}
    for child in children:
        if child.status == "active":
            continue
        label = year_names.get(child.left_club_year_id, "年度未設定")
        grouped.setdefault(label, []).append(child)
    order = [year.name for year in reversed(years) if year.name in grouped]
    if "年度未設定" in grouped:
        order.append("年度未設定")
    return [(label, grouped[label]) for label in order]


@admin_bp.route("/audit")
@require_admin_level(IMPORTANT_ADMIN_LEVEL)
def audit_log():
    club_id = session["club_id"]
    action_filter = request.args.get("action", "")
    query = AuditLog.query.filter_by(club_id=club_id)
    if action_filter:
        query = query.filter_by(action=action_filter)
    logs = query.order_by(AuditLog.at.desc()).limit(AUDIT_LOG_LIMIT).all()

    all_actions = sorted(
        {
            row.action
            for row in AuditLog.query.filter_by(club_id=club_id).with_entities(AuditLog.action).all()
        }
    )
    return render_template(
        "audit_log.html", logs=logs, all_actions=all_actions, action_filter=action_filter
    )


@admin_bp.route("/plan", methods=["GET", "POST"])
@require_admin_level(IMPORTANT_ADMIN_LEVEL)
def plan_view():
    """契約プランの確認・変更。Feature Flagの判定はこのSubscriptionを元に行う。"""
    club_id = session["club_id"]
    plans = Plan.query.order_by(Plan.monthly_yen).all()
    form = PlanChangeForm()
    form.plan_id.choices = [(plan.id, f"{plan.name}（月額{plan.monthly_yen}円）") for plan in plans]

    subscription = Subscription.query.filter_by(club_id=club_id).first()
    if request.method == "GET" and subscription is not None:
        form.plan_id.data = subscription.plan_id

    if form.validate_on_submit():
        if subscription is None:
            subscription = Subscription(club_id=club_id, plan_id=form.plan_id.data, state="active")
        else:
            subscription.plan_id = form.plan_id.data
            subscription.state = "active"
        db.session.add(subscription)
        log_action(club_id, current_user.id, "plan_changed", "Subscription", subscription.id)
        db.session.commit()
        return redirect(url_for("admin.plan_view"))

    current_plan = Plan.query.get(subscription.plan_id) if subscription else None
    return render_template(
        "plan_view.html",
        plans=plans,
        subscription=subscription,
        current_plan=current_plan,
        form=form,
        comparison_rows=_plan_comparison_rows(plans),
    )


def _plan_comparison_rows(plans) -> list:
    """全プランを横並びで比較する表データを作る（1つの比較表用）。"""
    rows = [
        {"label": "月額", "cells": [f"{plan.monthly_yen}円" for plan in plans]},
        {
            "label": "登録人数の上限",
            "cells": [f"{plan.member_cap}人" if plan.member_cap else "上限なし" for plan in plans],
        },
    ]
    feature_labels = {
        "camp": "合宿機能（合宿費・支出・持ち物リスト管理）",
        "csv_export": "請求CSV出力",
        "ocr": "予定表の写真アップロード＋OCRテキスト抽出",
        "multi_team": "複数チーム管理",
    }
    for key, label in feature_labels.items():
        cells = []
        for plan in plans:
            allowed = (
                PlanFeature.query.filter_by(plan_id=plan.id, feature_key=key, allowed=True).first()
                is not None
            )
            cells.append("✅" if allowed else "－")
        rows.append({"label": label, "cells": cells})
    return rows


def _upsert_admin_role(club_id: int, guardian_id: int, name: str, level: str) -> None:
    guardian = _get_guardian_or_404(club_id, guardian_id)
    role = AdminRole.query.filter_by(club_id=club_id, user_id=guardian.user_id).first()
    if role is None:
        role = AdminRole(club_id=club_id, user_id=guardian.user_id, name=name, level=level)
    else:
        role.name = name
        role.level = level
    db.session.add(role)
    log_action(club_id, current_user.id, "admin_role_updated", "AdminRole", guardian.user_id)
    db.session.commit()


def _remove_admin_role(club_id: int, guardian_id: int) -> None:
    guardian = _get_guardian_or_404(club_id, guardian_id)
    role = AdminRole.query.filter_by(club_id=club_id, user_id=guardian.user_id).first()
    if role is None:
        return

    if role.level == IMPORTANT_ADMIN_LEVEL:
        important_count = AdminRole.query.filter_by(
            club_id=club_id, level=IMPORTANT_ADMIN_LEVEL
        ).count()
        if important_count <= 1:
            abort(422)

    db.session.delete(role)
    log_action(club_id, current_user.id, "admin_role_removed", "AdminRole", guardian.user_id)
    db.session.commit()


def _get_guardian_or_404(club_id: int, guardian_id: int) -> Guardian:
    guardian = Guardian.query.get_or_404(guardian_id)
    if guardian.club_id != club_id:
        abort(404)
    return guardian
