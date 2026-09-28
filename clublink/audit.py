from typing import Optional

from clublink.extensions import db
from clublink.models import AuditLog


def log_action(
    club_id: int,
    user_id: int,
    action: str,
    target_type: str,
    target_id: Optional[int] = None,
    before: Optional[str] = None,
    after: Optional[str] = None,
) -> None:
    """監査ログを1行追加する。DB反映は呼び出し側の db.session.commit() で行う。"""
    db.session.add(
        AuditLog(
            club_id=club_id,
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before=before,
            after=after,
        )
    )
