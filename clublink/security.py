from functools import wraps
from typing import Callable, Optional

from flask import abort, session
from flask_login import current_user

from clublink.models import AdminRole

LEVEL_RANK = {"閲覧": 1, "編集": 2, "重要管理": 3}


def current_club_id() -> Optional[int]:
    """セッションに保存された現在のクラブID。"""
    return session.get("club_id")


def require_login_guardian(view: Callable) -> Callable:
    """ログイン済み・クラブ所属済みであることを要求する。"""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if current_club_id() is None:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def is_preview_mode() -> bool:
    """一般保護者としてのプレビュー中かどうか（管理者向けの動作確認機能）。"""
    return bool(session.get("preview_mode"))


def require_admin_level(min_level: str) -> Callable:
    """指定レベル以上の管理者権限を要求するデコレータファクトリ。プレビュー中は常に拒否する。"""

    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapped(*args, **kwargs):
            club_id = current_club_id()
            if not current_user.is_authenticated or club_id is None:
                abort(401)
            if is_preview_mode():
                abort(403)
            role = AdminRole.query.filter_by(club_id=club_id, user_id=current_user.id).first()
            if role is None or LEVEL_RANK[role.level] < LEVEL_RANK[min_level]:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
