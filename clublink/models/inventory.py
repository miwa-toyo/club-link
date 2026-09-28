from typing import List, Tuple

from clublink.extensions import db

INVENTORY_CATEGORIES = ("保護者用", "子供用")


class InventoryItem(db.Model):
    """部の備品。保護者用/子供用にカテゴリ分けできる。"""

    __tablename__ = "inventory_items"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    count = db.Column(db.Integer, default=0, nullable=False)
    location_text = db.Column(db.String(255), default="", nullable=False)
    category = db.Column(db.String(20), default="子供用", nullable=False)


def group_items_by_category(items: List["InventoryItem"]) -> List[Tuple[str, List["InventoryItem"]]]:
    """物品をカテゴリごとにまとめる（保護者用→子供用の順）。見出しは「用」を省いて返す。"""
    grouped: dict = {}
    for item in items:
        grouped.setdefault(item.category, []).append(item)
    ordered = [cat for cat in INVENTORY_CATEGORIES if cat in grouped]
    ordered += [cat for cat in grouped if cat not in INVENTORY_CATEGORIES]
    return [(category.replace("用", ""), grouped[category]) for category in ordered]
