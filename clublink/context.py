from flask import abort, session
from flask_login import current_user

from clublink.models import AdminRole, Guardian
from clublink.security import LEVEL_RANK, is_preview_mode


def current_guardian() -> Guardian:
    """現在ログイン中のユーザーの、現在のクラブにおける Guardian レコードを返す。"""
    guardian = Guardian.query.filter_by(
        club_id=session["club_id"], user_id=current_user.id
    ).first()
    if guardian is None:
        abort(403)
    return guardian


def _my_role() -> "AdminRole | None":
    return AdminRole.query.filter_by(club_id=session["club_id"], user_id=current_user.id).first()


def is_editor() -> bool:
    """現在のクラブで「編集」以上の管理者権限を持つか。プレビュー中は常にFalse。"""
    if is_preview_mode():
        return False
    role = _my_role()
    return role is not None and LEVEL_RANK[role.level] >= LEVEL_RANK["編集"]


def is_admin() -> bool:
    """現在のクラブで何らかの管理者権限（閲覧以上）を持つか。プレビュー中は常にFalse。"""
    if is_preview_mode():
        return False
    return _my_role() is not None


def is_important_admin() -> bool:
    """現在のクラブで「重要管理」権限を持つか。プレビュー中は常にFalse。"""
    if is_preview_mode():
        return False
    role = _my_role()
    return role is not None and role.level == "重要管理"


def can_start_preview() -> bool:
    """プレビュー開始ボタンを出してよいか（実際の権限で判定。プレビュー中でも実権限はここで確認できる）。"""
    role = _my_role()
    return role is not None and LEVEL_RANK[role.level] >= LEVEL_RANK["編集"]


def require_editor() -> None:
    """「編集」以上の権限がなければ403で中断する。プレビュー中も403にする。"""
    if not is_editor():
        abort(403)
