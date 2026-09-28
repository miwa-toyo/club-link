from datetime import datetime

from clublink.extensions import db

CAMP_FEE_STATUSES = ("未払い", "支払い済み")
EXPENSE_KINDS = ("食費", "補食", "その他")


class Camp(db.Model):
    """合宿・遠征。"""

    __tablename__ = "camps"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False, index=True)
    title = db.Column(db.String(100), nullable=False)
    starts_on = db.Column(db.Date, nullable=False)
    ends_on = db.Column(db.Date, nullable=False)
    place_text = db.Column(db.String(255), default="", nullable=False)


class PackingItem(db.Model):
    """持ち物リストの項目。target_count が 0 なら一覧に表示しない運用。"""

    __tablename__ = "packing_items"

    id = db.Column(db.Integer, primary_key=True)
    camp_id = db.Column(db.Integer, db.ForeignKey("camps.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    target_count = db.Column(db.Integer, default=0, nullable=False)


DEFAULT_CAMP_FEE_CATEGORIES = ("バス代", "宿泊費", "キャンセル料", "交通費")


class CampFeeCategory(db.Model):
    """合宿費の項目名。合宿ごとに自由に追加・名称変更できる（固定4項目からの変更）。"""

    __tablename__ = "camp_fee_categories"

    id = db.Column(db.Integer, primary_key=True)
    camp_id = db.Column(db.Integer, db.ForeignKey("camps.id"), nullable=False, index=True)
    label = db.Column(db.String(50), nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)


class CampFee(db.Model):
    """保護者ごとの合宿費レコード。金額の内訳は CampFeeAmount 側の可変項目で持つ。"""

    __tablename__ = "camp_fees"
    __table_args__ = (
        db.UniqueConstraint("camp_id", "guardian_id", name="uq_camp_fee_guardian"),
    )

    id = db.Column(db.Integer, primary_key=True)
    camp_id = db.Column(db.Integer, db.ForeignKey("camps.id"), nullable=False, index=True)
    guardian_id = db.Column(db.Integer, db.ForeignKey("guardians.id"), nullable=False, index=True)
    memo = db.Column(db.String(255), default="", nullable=False)
    paid_on = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(10), default="未払い", nullable=False)

    amounts = db.relationship(
        "CampFeeAmount", backref="camp_fee", cascade="all, delete-orphan"
    )

    @property
    def total_yen(self) -> int:
        return sum(amount.amount_yen for amount in self.amounts)


class CampFeeAmount(db.Model):
    """保護者×項目 ごとの金額。項目（CampFeeCategory）は合宿ごとに自由に定義される。"""

    __tablename__ = "camp_fee_amounts"
    __table_args__ = (
        db.UniqueConstraint("camp_fee_id", "category_id", name="uq_camp_fee_amount"),
    )

    id = db.Column(db.Integer, primary_key=True)
    camp_fee_id = db.Column(db.Integer, db.ForeignKey("camp_fees.id"), nullable=False, index=True)
    category_id = db.Column(
        db.Integer, db.ForeignKey("camp_fee_categories.id"), nullable=False, index=True
    )
    amount_yen = db.Column(db.Integer, default=0, nullable=False)


class CampExpense(db.Model):
    """合宿の支出。登録と同時に会計へ連携する。"""

    __tablename__ = "camp_expenses"

    id = db.Column(db.Integer, primary_key=True)
    camp_id = db.Column(db.Integer, db.ForeignKey("camps.id"), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False)
    amount_yen = db.Column(db.Integer, nullable=False)
    memo = db.Column(db.String(255), default="", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
