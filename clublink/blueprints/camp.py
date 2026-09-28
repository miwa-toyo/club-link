from datetime import date

from flask import Blueprint, abort, redirect, render_template, request, session, url_for

from clublink.context import is_editor, require_editor
from clublink.extensions import db
from clublink.features import has_feature
from clublink.forms import CampExpenseGridForm, CampFeeGridForm, CampForm, PackingGridForm
from clublink.models import (
    AccountingEntry,
    Camp,
    CampExpense,
    CampFee,
    CampFeeAmount,
    CampFeeCategory,
    Guardian,
    PackingItem,
)
from clublink.models.camp import CAMP_FEE_STATUSES, DEFAULT_CAMP_FEE_CATEGORIES, EXPENSE_KINDS
from clublink.models.fee import SOURCE_TYPE_CAMP_EXPENSE, SOURCE_TYPE_CAMP_FEE
from clublink.security import require_admin_level, require_login_guardian

camp_bp = Blueprint("camp", __name__, url_prefix="/camps")

NEW_CATEGORY_FIELD = "new_category_label"


@camp_bp.route("")
@require_login_guardian
def camp_list():
    """合宿一覧の表示（閲覧のみ）。新規作成は管理者ホーム経由の /camps/new で行う。"""
    camps = (
        Camp.query.filter_by(club_id=session["club_id"]).order_by(Camp.starts_on.desc()).all()
    )
    return render_template("camp_list.html", camps=camps)


@camp_bp.route("/new", methods=["GET", "POST"])
@require_admin_level("編集")
def camp_new():
    """合宿の新規作成。作成時に全保護者分のCampFeeと既定の費目を一括生成する。"""
    if not has_feature(session["club_id"], "camp"):
        abort(403)

    form = CampForm()
    if form.validate_on_submit():
        camp = Camp(
            club_id=session["club_id"],
            title=form.title.data,
            starts_on=form.starts_on.data,
            ends_on=form.ends_on.data,
            place_text=form.place_text.data or "",
        )
        db.session.add(camp)
        db.session.flush()
        categories = _create_default_categories(camp)
        _create_camp_fees_for_all_guardians(camp, categories)
        db.session.commit()
        return redirect(url_for("camp.camp_list"))

    return render_template("camp_new.html", form=form)


@camp_bp.route("/<int:camp_id>")
@require_login_guardian
def camp_edit(camp_id: int):
    camp = _get_camp_or_404(camp_id)
    return render_template("camp_detail.html", camp=camp, can_edit=is_editor())


@camp_bp.route("/<int:camp_id>/fees", methods=["GET", "POST"])
@require_admin_level("編集")
def camp_fees_grid(camp_id: int):
    """合宿費のExcel風一覧編集。費目名は自由に追加・変更でき、金額と支払状況を一括保存する。"""
    camp = _get_camp_or_404(camp_id)
    grid_form = CampFeeGridForm()

    if request.method == "POST":
        if not grid_form.validate_on_submit():
            abort(400)
        _rename_categories(camp)
        _add_new_category_if_present(camp)
        for fee in CampFee.query.filter_by(camp_id=camp.id).all():
            _update_camp_fee_from_form(camp, fee)
        db.session.commit()
        return redirect(url_for("camp.camp_fees_grid", camp_id=camp.id))

    categories = (
        CampFeeCategory.query.filter_by(camp_id=camp.id).order_by(CampFeeCategory.sort_order).all()
    )
    fees = (
        db.session.query(CampFee, Guardian)
        .join(Guardian, CampFee.guardian_id == Guardian.id)
        .filter(CampFee.camp_id == camp.id)
        .order_by(Guardian.display_name)
        .all()
    )
    amounts_by_fee = {
        fee.id: {amount.category_id: amount.amount_yen for amount in fee.amounts}
        for fee, _ in fees
    }
    return render_template(
        "camp_fees_grid.html",
        camp=camp,
        categories=categories,
        fees=fees,
        amounts_by_fee=amounts_by_fee,
        form=grid_form,
    )


@camp_bp.route("/<int:camp_id>/expenses", methods=["GET", "POST"])
@require_login_guardian
def expense_add(camp_id: int):
    """合宿の支出を家計簿のように1画面で編集する（更新・削除・新規追加を一括保存）。"""
    camp = _get_camp_or_404(camp_id)
    grid_form = CampExpenseGridForm()
    if request.method == "POST":
        require_editor()
        if not grid_form.validate_on_submit():
            abort(400)
        _update_expenses_from_form(camp)
        _add_new_expense_if_present(camp)
        db.session.commit()
        return redirect(url_for("camp.expense_add", camp_id=camp.id))

    expenses = (
        CampExpense.query.filter_by(camp_id=camp.id).order_by(CampExpense.created_at.desc()).all()
    )
    return render_template(
        "camp_expenses.html", camp=camp, expenses=expenses, form=grid_form, can_post=is_editor()
    )


@camp_bp.route("/<int:camp_id>/settle")
@require_login_guardian
def settle_calc(camp_id: int):
    """収支精算。支払い済みの合宿費合計 − 支出合計 = 収支。"""
    camp = _get_camp_or_404(camp_id)
    total_fees = sum(
        fee.total_yen
        for fee in CampFee.query.filter_by(camp_id=camp.id, status="支払い済み").all()
    )
    total_expenses = sum(
        expense.amount_yen for expense in CampExpense.query.filter_by(camp_id=camp.id).all()
    )
    return render_template(
        "camp_settle.html",
        camp=camp,
        total_fees=total_fees,
        total_expenses=total_expenses,
        balance=total_fees - total_expenses,
    )


@camp_bp.route("/<int:camp_id>/packing", methods=["GET", "POST"])
@require_login_guardian
def packing_master(camp_id: int):
    """持ち物リストを1画面で一括編集する（更新・新規追加をまとめて保存）。"""
    camp = _get_camp_or_404(camp_id)
    grid_form = PackingGridForm()
    if request.method == "POST":
        require_editor()
        if not grid_form.validate_on_submit():
            abort(400)
        _update_packing_items_from_form(camp)
        _add_new_packing_item_if_present(camp)
        db.session.commit()
        return redirect(url_for("camp.packing_master", camp_id=camp.id))

    items = PackingItem.query.filter_by(camp_id=camp.id).order_by(PackingItem.id).all()
    return render_template(
        "camp_packing.html", camp=camp, items=items, form=grid_form, can_post=is_editor()
    )


def _create_default_categories(camp: Camp) -> list:
    categories = []
    for order, label in enumerate(DEFAULT_CAMP_FEE_CATEGORIES):
        category = CampFeeCategory(camp_id=camp.id, label=label, sort_order=order)
        db.session.add(category)
        categories.append(category)
    db.session.flush()
    return categories


def _create_camp_fees_for_all_guardians(camp: Camp, categories: list) -> None:
    for guardian in Guardian.query.filter_by(club_id=camp.club_id).all():
        fee = CampFee(camp_id=camp.id, guardian_id=guardian.id)
        db.session.add(fee)
        db.session.flush()
        for category in categories:
            db.session.add(CampFeeAmount(camp_fee_id=fee.id, category_id=category.id, amount_yen=0))


def _rename_categories(camp: Camp) -> None:
    """列見出し（費目名）は自由記述に変更できる。空欄は変更しない。"""
    for category in CampFeeCategory.query.filter_by(camp_id=camp.id).all():
        new_label = request.form.get(f"category_label_{category.id}", "").strip()
        if new_label:
            category.label = new_label
            db.session.add(category)


def _add_new_category_if_present(camp: Camp) -> None:
    """自由記入欄に新しい費目名が入力されていれば、列を1つ追加する。"""
    new_label = request.form.get(NEW_CATEGORY_FIELD, "").strip()
    if not new_label:
        return

    max_order = (
        db.session.query(db.func.max(CampFeeCategory.sort_order))
        .filter_by(camp_id=camp.id)
        .scalar()
    )
    category = CampFeeCategory(camp_id=camp.id, label=new_label, sort_order=(max_order or -1) + 1)
    db.session.add(category)
    db.session.flush()

    for fee in CampFee.query.filter_by(camp_id=camp.id).all():
        db.session.add(CampFeeAmount(camp_fee_id=fee.id, category_id=category.id, amount_yen=0))


def _update_camp_fee_from_form(camp: Camp, fee: CampFee) -> None:
    for amount in fee.amounts:
        amount.amount_yen = _form_int(f"amount_{fee.id}_{amount.category_id}")
        db.session.add(amount)

    new_status = request.form.get(f"status_{fee.id}")
    if new_status in CAMP_FEE_STATUSES:
        _apply_camp_fee_status(camp, fee, new_status)


def _apply_camp_fee_status(camp: Camp, fee: CampFee, status: str) -> None:
    """支払状況を更新し、会計仕訳を UPSERT/削除する（部費と同じくR2の二重計上防止パターン）。"""
    if fee.status == status:
        return

    fee.status = status
    fee.paid_on = date.today() if status == "支払い済み" else None
    db.session.add(fee)

    entry = AccountingEntry.query.filter_by(
        source_type=SOURCE_TYPE_CAMP_FEE, source_ref_id=fee.id
    ).first()

    if status == "支払い済み":
        if entry is None:
            entry = AccountingEntry(
                club_id=camp.club_id,
                kind="収入",
                amount_yen=fee.total_yen,
                source_type=SOURCE_TYPE_CAMP_FEE,
                source_ref_id=fee.id,
                memo=f"{camp.title} 合宿費",
            )
        else:
            entry.amount_yen = fee.total_yen
        db.session.add(entry)
    elif entry is not None:
        db.session.delete(entry)


def _update_expenses_from_form(camp: Camp) -> None:
    """既存の支出行を更新する。delete_<id> にチェックがあれば支出と連携する仕訳ごと削除する。"""
    for expense in CampExpense.query.filter_by(camp_id=camp.id).all():
        if request.form.get(f"delete_{expense.id}"):
            _delete_expense_and_entry(expense)
            continue

        kind = request.form.get(f"kind_{expense.id}", expense.kind)
        if kind in EXPENSE_KINDS:
            expense.kind = kind
        expense.amount_yen = _form_int(f"amount_{expense.id}", expense.amount_yen)
        expense.memo = request.form.get(f"memo_{expense.id}", expense.memo) or ""
        db.session.add(expense)
        _sync_expense_accounting_entry(camp, expense)


def _add_new_expense_if_present(camp: Camp) -> None:
    amount_raw = request.form.get("new_amount", "").strip()
    if not amount_raw:
        return

    kind = request.form.get("new_kind", EXPENSE_KINDS[0])
    if kind not in EXPENSE_KINDS:
        kind = EXPENSE_KINDS[0]

    expense = CampExpense(
        camp_id=camp.id,
        kind=kind,
        amount_yen=_form_int("new_amount"),
        memo=request.form.get("new_memo", "") or "",
    )
    db.session.add(expense)
    db.session.flush()
    _sync_expense_accounting_entry(camp, expense)


def _sync_expense_accounting_entry(camp: Camp, expense: CampExpense) -> None:
    """支出1件につき会計仕訳1件をUPSERTする（source_type+source_ref_idで二重計上を防止：R2対策）。"""
    entry = AccountingEntry.query.filter_by(
        source_type=SOURCE_TYPE_CAMP_EXPENSE, source_ref_id=expense.id
    ).first()
    if entry is None:
        entry = AccountingEntry(
            club_id=camp.club_id,
            kind="支出",
            source_type=SOURCE_TYPE_CAMP_EXPENSE,
            source_ref_id=expense.id,
        )
    entry.amount_yen = expense.amount_yen
    entry.memo = f"{camp.title} {expense.kind}"
    db.session.add(entry)


def _delete_expense_and_entry(expense: CampExpense) -> None:
    entry = AccountingEntry.query.filter_by(
        source_type=SOURCE_TYPE_CAMP_EXPENSE, source_ref_id=expense.id
    ).first()
    if entry is not None:
        db.session.delete(entry)
    db.session.delete(expense)


def _update_packing_items_from_form(camp: Camp) -> None:
    for item in PackingItem.query.filter_by(camp_id=camp.id).all():
        if request.form.get(f"delete_{item.id}"):
            db.session.delete(item)
            continue
        name = request.form.get(f"name_{item.id}", "").strip()
        if name:
            item.name = name
        item.target_count = _form_int(f"count_{item.id}", item.target_count)
        db.session.add(item)


def _add_new_packing_item_if_present(camp: Camp) -> None:
    name = request.form.get("new_name", "").strip()
    if not name:
        return
    db.session.add(
        PackingItem(camp_id=camp.id, name=name, target_count=_form_int("new_count", 1))
    )


def _form_int(field_name: str, default: int = 0) -> int:
    value = request.form.get(field_name)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_camp_or_404(camp_id: int) -> Camp:
    camp = Camp.query.get_or_404(camp_id)
    if camp.club_id != session["club_id"]:
        abort(404)
    return camp
