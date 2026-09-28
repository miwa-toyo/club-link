from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from clublink.audit import log_action
from clublink.extensions import db
from clublink.forms import JoinForm, LoginForm, OnboardingForm, RegisterForm
from clublink.models import AdminRole, Child, Club, ClubYear, Guardian, Team, User
from clublink.models.billing import DEFAULT_SIGNUP_PLAN, Plan, Subscription
from clublink.models.club import generate_invite_code
from clublink.models.schedule import DEFAULT_TEAM_NAME

auth_bp = Blueprint("auth", __name__)

OWNER_ADMIN_LEVEL = "重要管理"


@auth_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("today.today_dashboard"))
    return render_template("index.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None or not user.check_password(form.password.data):
            flash("メールアドレスまたはパスワードが違います", "error")
            return render_template("login.html", form=form)
        _sign_in(user)
        return redirect(url_for("today.today_dashboard"))
    return render_template("login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("club_id", None)
    session.pop("preview_mode", None)
    return redirect(url_for("auth.index"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """新規クラブ作成 + オーナー登録。作成者は自動的に重要管理者になる。"""
    form = RegisterForm()
    if not form.validate_on_submit():
        return render_template("register.html", form=form)

    if User.query.filter_by(email=form.email.data).first() is not None:
        flash("このメールアドレスは既に登録されています", "error")
        return render_template("register.html", form=form)

    user = _create_user(form.email.data, form.password.data, form.display_name.data)
    club = _create_club(form.club_name.data, user)
    log_action(club.id, user.id, "club_created", "Club", club.id)
    db.session.commit()

    _sign_in(user)
    return redirect(url_for("auth.onboarding"))


@auth_bp.route("/invite", methods=["GET", "POST"])
def join_club():
    """招待コードで既存クラブに参加する。"""
    form = JoinForm()
    if not form.validate_on_submit():
        return render_template("invite.html", form=form)

    club = Club.query.filter_by(invite_code=form.invite_code.data).first()
    if club is None:
        flash("招待コードが見つかりません", "error")
        return render_template("invite.html", form=form)
    if User.query.filter_by(email=form.email.data).first() is not None:
        flash("このメールアドレスは既に登録されています", "error")
        return render_template("invite.html", form=form)

    user = _create_user(form.email.data, form.password.data, form.display_name.data)
    db.session.add(
        Guardian(club_id=club.id, user_id=user.id, display_name=form.display_name.data)
    )
    db.session.commit()

    _sign_in(user)
    return redirect(url_for("today.today_dashboard"))


@auth_bp.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    """クラブ作成直後の初回アンケート。最初のお子さまと送迎情報を登録する。"""
    club_id = session.get("club_id")
    if club_id is None:
        abort(403)

    form = OnboardingForm()
    if not form.validate_on_submit():
        return render_template("onboarding.html", form=form)

    guardian = Guardian.query.filter_by(club_id=club_id, user_id=current_user.id).first()
    if guardian is None:
        abort(403)

    child = Child(
        club_id=club_id,
        family_name=form.family_name.data,
        court_name=form.court_name.data,
        birth_date=form.birth_date.data,
        gender=form.gender.data,
        allergy=form.allergy.data or "",
    )
    child.guardians.append(guardian)
    db.session.add(child)

    guardian.can_drive = form.can_drive.data
    guardian.vehicle_seats = form.vehicle_seats.data or 0
    db.session.add(guardian)
    db.session.commit()

    flash("ご兄弟がいる場合は、マイページから追加登録できます。", "success")
    return redirect(url_for("mypage.mypage"))


def _sign_in(user: User) -> None:
    """ログイン処理とセッションへのclub_id固定をまとめて行う。"""
    guardian = Guardian.query.filter_by(user_id=user.id).first()
    if guardian is None:
        abort(403)
    login_user(user)
    session["club_id"] = guardian.club_id


def _create_user(email: str, password: str, display_name: str) -> User:
    user = User(email=email, display_name=display_name)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    return user


def _create_club(name: str, owner: User) -> Club:
    club = Club(name=name, invite_code=generate_invite_code(), owner_user_id=owner.id)
    db.session.add(club)
    db.session.flush()

    club_year = ClubYear(club_id=club.id, name=_current_year_label(), is_current=True)
    db.session.add(club_year)
    db.session.flush()

    db.session.add(Team(club_id=club.id, club_year_id=club_year.id, name=DEFAULT_TEAM_NAME))
    db.session.add(
        Guardian(club_id=club.id, user_id=owner.id, display_name=owner.display_name)
    )
    db.session.add(
        AdminRole(club_id=club.id, user_id=owner.id, name="代表", level=OWNER_ADMIN_LEVEL)
    )

    default_plan = Plan.query.filter_by(name=DEFAULT_SIGNUP_PLAN).first()
    if default_plan is not None:
        db.session.add(Subscription(club_id=club.id, plan_id=default_plan.id, state="trial"))

    return club


def _current_year_label() -> str:
    return f"{date.today().year}年度"
