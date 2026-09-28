"""クラブへのサンプルデータ投入ユーティリティ。

デモ専用アカウントを廃止した代わりに、既存の（実際に登録された）クラブに対して
管理者が任意のタイミングでサンプルのお知らせ・ルール・FAQ・予定・子供を投入できるようにする。
「プレビュー」機能と組み合わせることで、実際の登録フローのまま動作確認ができる。
"""

from datetime import date, datetime, timedelta

from clublink.extensions import db
from clublink.models import (
    FAQ,
    AbsenceReport,
    Announcement,
    Child,
    Club,
    Guardian,
    Rule,
    RuleVersion,
    Schedule,
    User,
    VehicleAssignment,
)
from clublink.models.schedule import get_default_team

SAMPLE_FEE_DEFAULT_YEN = 3000

_SAMPLE_ANNOUNCEMENTS = (
    ("来週の練習について", "来週の練習は雨天のため体育館で行います。", 1),
    ("部費のお願い", "今月分の部費を月末までにお納めください。", 3),
    ("夏合宿のご案内", "夏合宿の詳細を後日配布します。持ち物リストもご確認ください。", 7),
)

_SAMPLE_RULES = (
    ("練習", "練習は毎週土曜9:00〜11:00に体育館で行います。"),
    ("持ち物", "水筒・タオル・室内用シューズを必ずお持ちください。"),
)

_SAMPLE_FAQS = (
    ("持ち物は何がありますか？", "水筒、タオル、室内用シューズをお持ちください。", "持ち物", "持ち物,水筒"),
    ("部費はいくらですか？", "月額は男女で異なります。詳しくは部費設定をご確認ください。", "部費", "部費,料金"),
    ("見学はできますか？", "事前にご連絡いただければ、いつでも見学可能です。", "入会", "見学,入会"),
)

_SAMPLE_CHILDREN = (
    ("サンプル", "大輝", date(2014, 5, 10), "男子"),
    ("サンプル", "健太", date(2016, 8, 22), "男子"),
    ("サンプル", "美咲", date(2015, 3, 3), "女子"),
    ("サンプル", "さくら", date(2017, 11, 30), "女子"),
)

_SAMPLE_SCHEDULES = (
    # (種別, 場所, 送迎要否, 開始までの日数, 開始時刻の時)
    ("練習", "第一体育館", False, 2, 9),
    ("試合", "市営体育館", True, 10, 9),
)


def seed_sample_content(club: Club, owner: User) -> None:
    """お知らせ・ルール・FAQ・予定・子供のサンプルをまとめて投入する。呼び出し側でcommitすること。"""
    _seed_announcements(club, owner)
    _seed_rules(club, owner)
    _seed_faqs(club)
    _seed_children(club, owner)
    _seed_schedules(club)


def _seed_announcements(club: Club, owner: User) -> None:
    for title, body, days_ago in _SAMPLE_ANNOUNCEMENTS:
        db.session.add(
            Announcement(
                club_id=club.id,
                title=title,
                body=body,
                posted_by=owner.id,
                posted_at=datetime.utcnow() - timedelta(days=days_ago),
            )
        )


def _seed_rules(club: Club, owner: User) -> None:
    for category, body in _SAMPLE_RULES:
        rule = Rule(club_id=club.id, category=category, current_body=body)
        db.session.add(rule)
        db.session.flush()
        db.session.add(
            RuleVersion(rule_id=rule.id, before="", after=body, reason="初回登録", changed_by=owner.id)
        )


def _seed_faqs(club: Club) -> None:
    for question, answer, category, keywords in _SAMPLE_FAQS:
        db.session.add(
            FAQ(club_id=club.id, question=question, answer=answer, category=category, keywords=keywords)
        )


def _seed_children(club: Club, owner: User) -> None:
    guardian = Guardian.query.filter_by(club_id=club.id, user_id=owner.id).first()
    if guardian is None:
        return
    for family_name, court_name, birth_date, gender in _SAMPLE_CHILDREN:
        child = Child(
            club_id=club.id,
            family_name=family_name,
            court_name=court_name,
            birth_date=birth_date,
            gender=gender,
            status="active",
        )
        child.guardians.append(guardian)
        db.session.add(child)


def delete_sample_content(club_id: int) -> None:
    """seed_sample_content() で投入したサンプルデータを削除する。呼び出し側でcommitすること。

    サンプルデータ特有の値（お知らせのタイトル、ルールのカテゴリ/本文、FAQの質問、
    子供の苗字「サンプル」、予定の種別/場所の組み合わせ）に完全一致するものだけを対象とする。
    """
    _delete_sample_announcements(club_id)
    _delete_sample_rules(club_id)
    _delete_sample_faqs(club_id)
    _delete_sample_schedules(club_id)
    _delete_sample_children(club_id)


def _delete_sample_announcements(club_id: int) -> None:
    titles = {title for title, _, _ in _SAMPLE_ANNOUNCEMENTS}
    Announcement.query.filter(
        Announcement.club_id == club_id, Announcement.title.in_(titles)
    ).delete(synchronize_session=False)


def _delete_sample_rules(club_id: int) -> None:
    for category, body in _SAMPLE_RULES:
        rule = Rule.query.filter_by(club_id=club_id, category=category, current_body=body).first()
        if rule is None:
            continue
        RuleVersion.query.filter_by(rule_id=rule.id).delete()
        db.session.delete(rule)


def _delete_sample_faqs(club_id: int) -> None:
    questions = {question for question, _, _, _ in _SAMPLE_FAQS}
    FAQ.query.filter(FAQ.club_id == club_id, FAQ.question.in_(questions)).delete(
        synchronize_session=False
    )


def _delete_sample_schedules(club_id: int) -> None:
    for kind, place, needs_car, _, _ in _SAMPLE_SCHEDULES:
        schedules = Schedule.query.filter_by(
            club_id=club_id, kind=kind, place=place, needs_car=needs_car
        ).all()
        for schedule in schedules:
            AbsenceReport.query.filter_by(schedule_id=schedule.id).delete()
            VehicleAssignment.query.filter_by(schedule_id=schedule.id).delete()
            db.session.delete(schedule)


def _delete_sample_children(club_id: int) -> None:
    for child in Child.query.filter_by(club_id=club_id, family_name="サンプル").all():
        AbsenceReport.query.filter_by(child_id=child.id).delete()
        db.session.delete(child)


def _seed_schedules(club: Club) -> None:
    team = get_default_team(club.id)
    if team is None:
        return
    for kind, place, needs_car, days_from_now, hour in _SAMPLE_SCHEDULES:
        db.session.add(
            Schedule(
                club_id=club.id,
                team_id=team.id,
                kind=kind,
                starts_at=datetime.utcnow() + timedelta(days=days_from_now, hours=hour),
                place=place,
                needs_car=needs_car,
            )
        )
