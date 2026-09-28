from datetime import datetime

from clublink.extensions import db

SUBSCRIPTION_STATES = ("trial", "active", "past_due", "cancelled", "expired")
ACTIVE_STATES = ("trial", "active")


class Plan(db.Model):
    """課金プラン。Planはクラブに属さないグローバルなマスタデータ。"""

    __tablename__ = "plans"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    monthly_yen = db.Column(db.Integer, default=0, nullable=False)
    member_cap = db.Column(db.Integer, nullable=True)


class PlanFeature(db.Model):
    """プランごとのFeature Flag。Plan.name単体ではなくこのテーブルを機能判定の正とする。"""

    __tablename__ = "plan_features"
    __table_args__ = (
        db.UniqueConstraint("plan_id", "feature_key", name="uq_plan_feature"),
    )

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("plans.id"), nullable=False, index=True)
    feature_key = db.Column(db.String(50), nullable=False)
    allowed = db.Column(db.Boolean, default=False, nullable=False)


class Subscription(db.Model):
    """クラブの契約状態。1クラブにつき1件を想定。"""

    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), unique=True, nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey("plans.id"), nullable=False)
    state = db.Column(db.String(10), default="trial", nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# プラン名とFeature Flagの初期構成。クラブに依存しないため create_app() 起動時に一度だけ投入する。
DEFAULT_PLANS = {
    "無料": {"monthly_yen": 0, "member_cap": 20, "features": set()},
    "Standard": {
        "monthly_yen": 980,
        "member_cap": 100,
        "features": {"camp", "csv_export"},
    },
    "Pro": {
        "monthly_yen": 2980,
        "member_cap": None,
        "features": {"camp", "csv_export", "ocr", "multi_team"},
    },
}
DEFAULT_SIGNUP_PLAN = "Standard"


def ensure_default_plans() -> None:
    """既定の3プランとFeature Flagが無ければ作成する。冪等（何度呼んでも安全）。"""
    for name, spec in DEFAULT_PLANS.items():
        plan = Plan.query.filter_by(name=name).first()
        if plan is None:
            plan = Plan(name=name, monthly_yen=spec["monthly_yen"], member_cap=spec["member_cap"])
            db.session.add(plan)
            db.session.flush()
        for feature_key in spec["features"]:
            exists = PlanFeature.query.filter_by(plan_id=plan.id, feature_key=feature_key).first()
            if exists is None:
                db.session.add(PlanFeature(plan_id=plan.id, feature_key=feature_key, allowed=True))
    db.session.commit()
