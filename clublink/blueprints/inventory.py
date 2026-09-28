from flask import Blueprint, redirect, render_template, request, session, url_for

from clublink.context import is_editor, require_editor
from clublink.extensions import db
from clublink.models import InventoryItem
from clublink.models.inventory import INVENTORY_CATEGORIES, group_items_by_category
from clublink.security import require_login_guardian

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")


@inventory_bp.route("", methods=["GET", "POST"])
@require_login_guardian
def inventory_list():
    """部の備品一覧（全保護者に公開）。管理者は一覧上で一括更新・削除・新規追加できる。"""
    if request.method == "POST":
        require_editor()
        _update_items_from_form()
        _add_new_item_if_present()
        db.session.commit()
        return redirect(url_for("inventory.inventory_list"))

    items = (
        InventoryItem.query.filter_by(club_id=session["club_id"]).order_by(InventoryItem.name).all()
    )
    return render_template(
        "inventory_list.html",
        items=items,
        items_by_category=group_items_by_category(items),
        categories=INVENTORY_CATEGORIES,
        can_post=is_editor(),
    )


def _update_items_from_form() -> None:
    for item in InventoryItem.query.filter_by(club_id=session["club_id"]).all():
        if request.form.get(f"delete_{item.id}"):
            db.session.delete(item)
            continue
        name = request.form.get(f"name_{item.id}", "").strip()
        if name:
            item.name = name
        item.count = _form_int(f"count_{item.id}", item.count)
        item.location_text = request.form.get(f"location_{item.id}", item.location_text)
        category = request.form.get(f"category_{item.id}", item.category)
        if category in INVENTORY_CATEGORIES:
            item.category = category
        db.session.add(item)


def _add_new_item_if_present() -> None:
    name = request.form.get("new_name", "").strip()
    if not name:
        return
    category = request.form.get("new_category", INVENTORY_CATEGORIES[0])
    if category not in INVENTORY_CATEGORIES:
        category = INVENTORY_CATEGORIES[0]
    db.session.add(
        InventoryItem(
            club_id=session["club_id"],
            name=name,
            count=_form_int("new_count", 0),
            location_text=request.form.get("new_location", ""),
            category=category,
        )
    )


def _form_int(field_name: str, default: int = 0) -> int:
    value = request.form.get(field_name)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
