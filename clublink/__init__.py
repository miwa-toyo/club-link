from flask import Flask, abort, session
from flask_login import current_user

from clublink.blueprints.admin import admin_bp
from clublink.blueprints.auth import auth_bp
from clublink.blueprints.camp import camp_bp
from clublink.blueprints.fee import fee_bp
from clublink.blueprints.info import info_bp
from clublink.blueprints.inventory import inventory_bp
from clublink.blueprints.mypage import mypage_bp
from clublink.blueprints.ocr import ocr_bp
from clublink.blueprints.schedule import schedule_bp
from clublink.blueprints.team import team_bp
from clublink.blueprints.today import today_bp
from clublink.blueprints.vehicle import vehicle_bp
from clublink.config import Config
from clublink.context import is_admin, is_editor, is_important_admin
from clublink.extensions import csrf, db, login_manager
from clublink.models import Guardian, User


def create_app(config_class: type = Config) -> Flask:
    """アプリケーションファクトリ。テスト時は config_class を差し替える。"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"

    app.register_blueprint(auth_bp)
    app.register_blueprint(mypage_bp)
    app.register_blueprint(schedule_bp)
    app.register_blueprint(today_bp)
    app.register_blueprint(info_bp)
    app.register_blueprint(vehicle_bp)
    app.register_blueprint(fee_bp)
    app.register_blueprint(camp_bp)
    app.register_blueprint(team_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(ocr_bp)
    app.before_request(_guard_club_isolation)
    app.context_processor(_inject_is_editor)

    with app.app_context():
        db.create_all()
        from clublink.models import ensure_default_plans

        ensure_default_plans()

    return app


@login_manager.user_loader
def load_user(user_id: str) -> "User | None":
    return User.query.get(int(user_id))


def _guard_club_isolation() -> None:
    """セッションのclub_idが本人の所属クラブと一致しない場合は拒否する（R4対策）。"""
    if not current_user.is_authenticated:
        return
    club_id = session.get("club_id")
    if club_id is None:
        return
    is_member = Guardian.query.filter_by(club_id=club_id, user_id=current_user.id).first()
    if is_member is None:
        session.pop("club_id", None)
        abort(403)


def _inject_is_editor() -> dict:
    """テンプレートで管理者限定ナビの表示可否を判定するために公開する。"""
    if not current_user.is_authenticated or session.get("club_id") is None:
        return {"nav_is_editor": False, "nav_is_admin": False, "nav_is_important_admin": False}
    return {
        "nav_is_editor": is_editor(),
        "nav_is_admin": is_admin(),
        "nav_is_important_admin": is_important_admin(),
    }
