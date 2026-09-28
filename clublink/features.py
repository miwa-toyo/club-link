from clublink.models import PlanFeature, Subscription
from clublink.models.billing import ACTIVE_STATES


def has_feature(club_id: int, feature_key: str) -> bool:
    """クラブの契約プランが指定のFeature Flagを許可しているか判定する。

    契約が有効（trial/active）でない場合は、プラン内容によらず常に False とする。
    """
    subscription = Subscription.query.filter_by(club_id=club_id).first()
    if subscription is None or subscription.state not in ACTIVE_STATES:
        return False

    feature = PlanFeature.query.filter_by(
        plan_id=subscription.plan_id, feature_key=feature_key
    ).first()
    return feature is not None and feature.allowed
