from datetime import datetime

from clublink.extensions import db

PAYMENT_STATUSES = ("未納", "入金済み")
ENTRY_KINDS = ("収入", "支出")
SOURCE_TYPE_FEE = "部費"
SOURCE_TYPE_CAMP_FEE = "合宿費"
SOURCE_TYPE_CAMP_EXPENSE = "合宿支出"
SOURCE_TYPE_MANUAL = "手動"


class Fee(db.Model):
    """年月ごとの部費設定。男女で金額を分けられる（子供の人数分を合算してPaymentの金額を決める）。"""

    __tablename__ = "fees"
    __table_args__ = (
        db.UniqueConstraint("club_id", "year", "month", name="uq_fee_club_year_month"),
    )

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    amount_yen_male = db.Column(db.Integer, nullable=False)
    amount_yen_female = db.Column(db.Integer, nullable=False)


class Payment(db.Model):
    """保護者ごとの部費入金状況。1つのFeeにつき保護者1人1行。

    amount_yen は作成時点の子供の性別構成から計算した確定金額。入金済みの行は
    後からFeeの単価を変更しても遡って変わらない（会計の履歴性を優先）。
    """

    __tablename__ = "payments"
    __table_args__ = (
        db.UniqueConstraint("fee_id", "guardian_id", name="uq_payment_fee_guardian"),
    )

    id = db.Column(db.Integer, primary_key=True)
    fee_id = db.Column(db.Integer, db.ForeignKey("fees.id"), nullable=False, index=True)
    guardian_id = db.Column(db.Integer, db.ForeignKey("guardians.id"), nullable=False, index=True)
    amount_yen = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(10), default="未納", nullable=False)
    paid_on = db.Column(db.Date, nullable=True)


class AccountingCategory(db.Model):
    """会計カテゴリ名称。Phase B時点ではUIからの参照のみ（登録画面は今後追加）。"""

    __tablename__ = "accounting_categories"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)


class AccountingEntry(db.Model):
    """会計仕訳。source_type='部費' の行は Payment 入金確定時に自動生成・自動削除される。

    (source_type, source_ref_id) を一意にすることで二重計上を防ぐ（R2対策）。
    source_ref_id が NULL の手動入力行は複数存在してよい（DBのNULL非等価性により許可される）。
    """

    __tablename__ = "accounting_entries"
    __table_args__ = (
        db.UniqueConstraint("source_type", "source_ref_id", name="uq_entry_source"),
    )

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False, index=True)
    category_id = db.Column(
        db.Integer, db.ForeignKey("accounting_categories.id"), nullable=True
    )
    kind = db.Column(db.String(10), nullable=False)
    amount_yen = db.Column(db.Integer, nullable=False)
    source_type = db.Column(db.String(10), nullable=False)
    source_ref_id = db.Column(db.Integer, nullable=True)
    memo = db.Column(db.String(255), default="", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
