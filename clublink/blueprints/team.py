from flask import Blueprint, abort, redirect, render_template, request, session, url_for

from clublink.extensions import db
from clublink.forms import TeamForm
from clublink.models import Child, ClubYear, Team, TeamMember
from clublink.security import require_admin_level, require_login_guardian

team_bp = Blueprint("team", __name__, url_prefix="/teams")


@team_bp.route("", methods=["GET", "POST"])
@require_admin_level("編集")
def team_list():
    """チーム一覧の表示 + 新規作成（管理者限定）。"""
    club_id = session["club_id"]
    form = TeamForm()
    if form.validate_on_submit():
        current_year = ClubYear.query.filter_by(club_id=club_id, is_current=True).first()
        if current_year is None:
            abort(500)
        next_sort_order = _next_team_sort_order(club_id)
        db.session.add(
            Team(
                club_id=club_id,
                club_year_id=current_year.id,
                name=form.name.data,
                sort_order=next_sort_order,
            )
        )
        db.session.commit()
        return redirect(url_for("team.team_list"))

    teams = Team.query.filter_by(club_id=club_id).order_by(Team.sort_order).all()
    return render_template("team_list.html", teams=teams, form=form)


@team_bp.route("/compose", methods=["GET", "POST"])
@require_admin_level("編集")
def team_compose():
    """在籍中の子供のチーム所属を一括編成する。1子供につき所属チームは常に1つ。"""
    club_id = session["club_id"]
    teams = Team.query.filter_by(club_id=club_id).order_by(Team.sort_order).all()
    children = Child.query.filter_by(club_id=club_id, status="active").all()

    if request.method == "POST":
        valid_team_ids = {team.id for team in teams}
        for child in children:
            _assign_child_to_team(child.id, request.form.get(f"team_{child.id}"), valid_team_ids)
        db.session.commit()
        return redirect(url_for("team.team_compose"))

    memberships = {
        member.child_id: member.team_id
        for member in TeamMember.query.join(Team).filter(Team.club_id == club_id).all()
    }
    return render_template(
        "team_compose.html", teams=teams, children=children, memberships=memberships
    )


@team_bp.route("/<int:team_id>/members")
@require_login_guardian
def team_members(team_id: int):
    team = _get_team_or_404(team_id)
    members = (
        Child.query.join(TeamMember, TeamMember.child_id == Child.id)
        .filter(TeamMember.team_id == team.id)
        .all()
    )
    return render_template("team_members.html", team=team, members=members)


def _next_team_sort_order(club_id: int) -> int:
    max_order = (
        db.session.query(db.func.max(Team.sort_order)).filter_by(club_id=club_id).scalar()
    )
    return (max_order or -1) + 1


def _assign_child_to_team(child_id: int, team_id_raw: str, valid_team_ids: set) -> None:
    try:
        team_id = int(team_id_raw)
    except (TypeError, ValueError):
        return
    if team_id not in valid_team_ids:
        return

    membership = TeamMember.query.filter_by(child_id=child_id).first()
    if membership is None:
        db.session.add(TeamMember(team_id=team_id, child_id=child_id))
    elif membership.team_id != team_id:
        membership.team_id = team_id
        db.session.add(membership)


def _get_team_or_404(team_id: int) -> Team:
    team = Team.query.get_or_404(team_id)
    if team.club_id != session["club_id"]:
        abort(404)
    return team
