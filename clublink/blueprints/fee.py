import csv
import io
from datetime import date

from flask import Blueprint, Response, abort, redirect, render_template, request, session, url_for

from clublink.context import is_editor, require_editor
from clublink.extensions import db
from clublink.features import has_feature
from clublink.forms import FeeForm
from clublink.models import AccountingEntry, Fee, Guardian, Payment
from clublink.models.fee import ENTRY_KINDS, PAYMENT_STATUSES, SOURCE_TYPE_FEE, SOURCE_TYPE_MANUAL
from clublink.security import require_admin_level, require_login_guardian

fee_bp = Blueprint("fee", __name__, url_prefix="/accounting")


@fee_bp.route("/fees", methods=["GET", "POST"])
@require_admin_level("編集")
def fee_setting():
    """年月ごとの部費金額（男女別）を設定する。新規作成時に全保護者分のPaymentを一括生成する。"""
    form = FeeForm()
    if form.validate_on_submit():
        fee = Fee.query.filter_by(
            club_id=session["club_id"], year=form.year.data, month=form.month.data
        ).first()
        if fee is None:
            fee = Fee(
                club_id=session["club_id"],
                year=form.year.data,
                month=form.month.data,
                amount_yen_male=form.amount_yen_male.data,
                amount_yen_female=form.amount_yen_female.data,
            )
            db.session.add(fee)
            db.session.flush()
            _create_payments_for_all_guardians(fee)
        else:
            fee.amount_yen_male = form.amount_yen_male.data
            fee.amount_yen_female = form.amount_yen_female.data
            _refresh_unpaid_payment_amounts(fee)
        db.session.commit()
        return redirect(url_for("fee.fee_setting"))

    fees = (
        Fee.query.filter_by(club_id=session["club_id"])
        .order_by(Fee.year.desc(), Fee.month.desc())
        .all()
    )
    return render_template("fee_setting.html", fees=fees, form=form)


@fee_bp.route("/fees/<int:fee_id>/payments", methods=["GET", "POST"])
@require_admin_level("編集")
def payment_bulk_update(fee_id: int):
    """入金状況の一括更新。入金済みにすると会計へ自動連携し、取り消すと自動で仕訳も削除する。"""
    fee = _get_fee_or_404(fee_id)
    if request.method == "POST":
        for payment in Payment.query.filter_by(fee_id=fee.id).all():
            status = request.form.get(f"status_{payment.id}")
            if status in PAYMENT_STATUSES:
                _apply_payment_status(fee, payment, status)
        db.session.commit()
        return redirect(url_for("fee.payment_bulk_update", fee_id=fee.id))

    status_filter = request.args.get("status", "")
    payments = (
        db.session.query(Payment, Guardian)
        .join(Guardian, Payment.guardian_id == Guardian.id)
        .filter(Payment.fee_id == fee.id)
        .order_by(Guardian.display_name)
        .all()
    )
    if status_filter in PAYMENT_STATUSES:
        payments = [(p, g) for p, g in payments if p.status == status_filter]
    return render_template(
        "payment_bulk_update.html", fee=fee, payments=payments, status_filter=status_filter
    )


@fee_bp.route("/fees/billing.csv")
@require_admin_level("編集")
def billing_csv():
    """CSV出力はcsv_export Feature Flagを持つプランのみ利用可能（Standard以上）。"""
    club_id = session["club_id"]
    if not has_feature(club_id, "csv_export"):
        abort(403)

    rows = (
        db.session.query(Payment, Guardian, Fee)
        .join(Guardian, Payment.guardian_id == Guardian.id)
        .join(Fee, Payment.fee_id == Fee.id)
        .filter(Fee.club_id == club_id)
        .order_by(Fee.year, Fee.month, Guardian.display_name)
        .all()
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["年度", "月", "保護者", "金額", "状態", "入金日"])
    for payment, guardian, fee in rows:
        writer.writerow(
            [fee.year, fee.month, guardian.display_name, payment.amount_yen, payment.status, payment.paid_on or ""]
        )

    response = Response(buffer.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=billing_club{club_id}.csv"
    return response


@fee_bp.route("/allocations", methods=["GET", "POST"])
@require_login_guardian
def allocation_list():
    """会計仕訳の一覧表示（全保護者に公開）＋手動仕訳の一括更新・削除・新規追加（管理者限定）。

    部費・合宿費・合宿支出から自動生成された仕訳は、元のデータと食い違わないよう
    ここでは編集・削除できない（それぞれの画面で操作する）。手動入力分のみ編集対象。
    """
    if request.method == "POST":
        require_editor()
        _update_manual_entries_from_form()
        _add_new_manual_entry_if_present()
        db.session.commit()
        return redirect(url_for("fee.allocation_list"))

    entries = (
        AccountingEntry.query.filter_by(club_id=session["club_id"])
        .order_by(AccountingEntry.created_at.desc())
        .all()
    )
    return render_template(
        "allocation_list.html",
        entries=entries,
        can_post=is_editor(),
        summary=_compute_summary(entries),
        monthly_rows=_compute_monthly_rows(entries),
    )


def _compute_summary(entries) -> dict:
    """部費合計額・支出合計・現在の残高（繰越金）を計算する。"""
    total_income = sum(e.amount_yen for e in entries if e.kind == "収入")
    total_expense = sum(e.amount_yen for e in entries if e.kind == "支出")
    total_fee_income = sum(
        e.amount_yen for e in entries if e.source_type == SOURCE_TYPE_FEE and e.kind == "収入"
    )
    return {
        "total_fee_income": total_fee_income,
        "total_expense": total_expense,
        "current_balance": total_income - total_expense,
    }


def _compute_monthly_rows(entries) -> list:
    """月ごとの収入・支出・繰越金（前月からの残高）・残高（翌月への繰越金）をまとめる。
    仕訳がある月のみ、古い月から新しい月の順に並べる。
    """
    monthly: dict = {}
    for entry in entries:
        key = (entry.created_at.year, entry.created_at.month)
        bucket = monthly.setdefault(key, {"income": 0, "expense": 0})
        if entry.kind == "収入":
            bucket["income"] += entry.amount_yen
        else:
            bucket["expense"] += entry.amount_yen

    rows = []
    carryover = 0
    for year, month in sorted(monthly.keys()):
        bucket = monthly[(year, month)]
        balance = carryover + bucket["income"] - bucket["expense"]
        rows.append(
            {
                "label": f"{year}年{month}月",
                "carryover": carryover,
                "income": bucket["income"],
                "expense": bucket["expense"],
                "balance": balance,
            }
        )
        carryover = balance
    return rows


def _update_manual_entries_from_form() -> None:
    for entry in AccountingEntry.query.filter_by(
        club_id=session["club_id"], source_type=SOURCE_TYPE_MANUAL
    ).all():
        if request.form.get(f"delete_{entry.id}"):
            db.session.delete(entry)
            continue
        kind = request.form.get(f"kind_{entry.id}", entry.kind)
        if kind in ENTRY_KINDS:
            entry.kind = kind
        entry.amount_yen = _form_int(f"amount_{entry.id}", entry.amount_yen)
        entry.memo = request.form.get(f"memo_{entry.id}", entry.memo)
        db.session.add(entry)


def _add_new_manual_entry_if_present() -> None:
    amount_raw = request.form.get("new_amount", "").strip()
    if not amount_raw:
        return
    kind = request.form.get("new_kind", ENTRY_KINDS[0])
    if kind not in ENTRY_KINDS:
        kind = ENTRY_KINDS[0]
    db.session.add(
        AccountingEntry(
            club_id=session["club_id"],
            kind=kind,
            amount_yen=_form_int("new_amount"),
            source_type=SOURCE_TYPE_MANUAL,
            memo=request.form.get("new_memo", ""),
        )
    )


def _form_int(field_name: str, default: int = 0) -> int:
    value = request.form.get(field_name)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _amount_for_guardian(fee: Fee, guardian: Guardian) -> int:
    """保護者に紐づく子供の性別構成から、その保護者が支払う部費の合計額を計算する。"""
    total = 0
    for child in guardian.children:
        if child.status != "active":
            continue
        total += fee.amount_yen_male if child.gender == "男子" else fee.amount_yen_female
    return total


def _create_payments_for_all_guardians(fee: Fee) -> None:
    for guardian in Guardian.query.filter_by(club_id=fee.club_id).all():
        db.session.add(
            Payment(fee_id=fee.id, guardian_id=guardian.id, amount_yen=_amount_for_guardian(fee, guardian))
        )


def _refresh_unpaid_payment_amounts(fee: Fee) -> None:
    """未納の支払いのみ、変更後の単価で金額を再計算する（入金済みの記録は変更しない）。"""
    payments = (
        db.session.query(Payment, Guardian)
        .join(Guardian, Payment.guardian_id == Guardian.id)
        .filter(Payment.fee_id == fee.id, Payment.status == "未納")
        .all()
    )
    for payment, guardian in payments:
        payment.amount_yen = _amount_for_guardian(fee, guardian)
        db.session.add(payment)


def _apply_payment_status(fee: Fee, payment: Payment, status: str) -> None:
    """入金状況を更新し、会計仕訳を (source_type, source_ref_id) でUPSERTする（二重計上防止：R2対策）。"""
    if payment.status == status:
        return

    payment.status = status
    payment.paid_on = date.today() if status == "入金済み" else None
    db.session.add(payment)

    entry = AccountingEntry.query.filter_by(
        source_type=SOURCE_TYPE_FEE, source_ref_id=payment.id
    ).first()

    if status == "入金済み":
        if entry is None:
            entry = AccountingEntry(
                club_id=fee.club_id,
                kind="収入",
                amount_yen=payment.amount_yen,
                source_type=SOURCE_TYPE_FEE,
                source_ref_id=payment.id,
                memo=f"{fee.year}年{fee.month}月分部費",
            )
        else:
            entry.amount_yen = payment.amount_yen
        db.session.add(entry)
    elif entry is not None:
        db.session.delete(entry)


def _get_fee_or_404(fee_id: int) -> Fee:
    fee = Fee.query.get_or_404(fee_id)
    if fee.club_id != session["club_id"]:
        abort(404)
    return fee
