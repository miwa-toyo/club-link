from typing import List, Optional

from flask import Blueprint, abort, redirect, render_template, request, session, url_for
from flask_login import current_user

from clublink.audit import log_action
from clublink.context import is_editor, require_editor
from clublink.extensions import db
from clublink.forms import AnnouncementForm
from clublink.models import FAQ, Announcement, ClubSetting, InventoryItem, Rule, RuleVersion
from clublink.models.inventory import INVENTORY_CATEGORIES, group_items_by_category
from clublink.security import require_admin_level, require_login_guardian

info_bp = Blueprint("info", __name__)

RECENT_ANNOUNCEMENT_LIMIT = 20


@info_bp.route("/announcements", methods=["GET", "POST"])
@require_login_guardian
def announcement_post():
    """お知らせ一覧の表示 + 新規投稿・編集（管理者限定）。announcement_id が送られれば既存の更新。"""
    form = AnnouncementForm()
    if request.method == "POST":
        require_editor()
        if form.validate_on_submit():
            _save_announcement(form, request.form.get("announcement_id", type=int))
            return redirect(url_for("info.announcement_post"))

    announcements = (
        Announcement.query.filter_by(club_id=session["club_id"])
        .order_by(Announcement.posted_at.desc())
        .limit(RECENT_ANNOUNCEMENT_LIMIT)
        .all()
    )
    return render_template(
        "announcements.html", announcements=announcements, form=form, can_post=is_editor()
    )


@info_bp.route("/announcements/<int:announcement_id>/delete", methods=["POST"])
@require_admin_level("編集")
def announcement_delete(announcement_id: int):
    announcement = Announcement.query.get_or_404(announcement_id)
    if announcement.club_id != session["club_id"]:
        abort(404)
    db.session.delete(announcement)
    db.session.commit()
    return redirect(url_for("info.announcement_post"))


@info_bp.route("/support", methods=["GET", "POST"])
@require_admin_level("閲覧")
def support():
    """お問い合わせ窓口・システムのよくある質問。管理者ホームからのみ辿れる（一般保護者には非公開）。
    連絡先は編集権限以上が編集できる。
    """
    club_id = session["club_id"]
    setting = ClubSetting.query.get(club_id)

    if request.method == "POST":
        require_editor()
        if setting is None:
            setting = ClubSetting(club_id=club_id)
        setting.contact_info = request.form.get("contact_info", "").strip()
        db.session.add(setting)
        db.session.commit()
        return redirect(url_for("info.support"))

    return render_template(
        "support.html",
        contact_info=setting.contact_info if setting else "",
        can_edit=is_editor(),
    )


@info_bp.route("/rules-faq")
@require_login_guardian
def rules_faq():
    """ルール・FAQ・物品の一覧。カテゴリで絞り込める。

    一般保護者にはカテゴリ見出し＋箇条書きで表示し、管理者には物品管理と同じ
    一括編集グリッド（更新・削除・新規追加をまとめて1回で保存）を表示する。
    """
    club_id = session["club_id"]
    category_filter = request.args.get("category", "").strip()
    rule_keyword = request.args.get("q", "").strip()

    rules_query = Rule.query.filter_by(club_id=club_id)
    faqs_query = FAQ.query.filter_by(club_id=club_id)
    items_query = InventoryItem.query.filter_by(club_id=club_id)
    if category_filter:
        rules_query = rules_query.filter_by(category=category_filter)
        faqs_query = faqs_query.filter_by(category=category_filter)
        items_query = items_query.filter_by(category=category_filter)
    if rule_keyword:
        pattern = f"%{rule_keyword}%"
        rules_query = rules_query.filter(
            db.or_(Rule.category.like(pattern), Rule.current_body.like(pattern))
        )

    rules = rules_query.order_by(Rule.category, Rule.id).all()
    faqs = faqs_query.order_by(FAQ.category, FAQ.id).all()
    items = items_query.order_by(InventoryItem.category, InventoryItem.name).all()

    all_categories = sorted(
        {rule.category for rule in Rule.query.filter_by(club_id=club_id).all()}
        | {faq.category for faq in FAQ.query.filter_by(club_id=club_id).all() if faq.category}
        | set(INVENTORY_CATEGORIES)
    )

    return render_template(
        "rules_faq.html",
        rules=rules,
        faqs=faqs,
        rule_keyword=rule_keyword,
        rules_by_category=_group_by_category(rules),
        faqs_by_category=_group_by_category(faqs),
        items_by_category=group_items_by_category(items),
        all_categories=all_categories,
        category_filter=category_filter,
        can_edit=is_editor(),
    )


@info_bp.route("/rules/bulk", methods=["POST"])
@require_admin_level("編集")
def rule_bulk_save():
    """ルールを一覧上でまとめて更新・削除・新規追加する（物品管理と同じ一括保存方式）。"""
    club_id = session["club_id"]
    for rule in Rule.query.filter_by(club_id=club_id).all():
        if request.form.get(f"delete_{rule.id}"):
            RuleVersion.query.filter_by(rule_id=rule.id).delete()
            db.session.delete(rule)
            continue
        category = request.form.get(f"category_{rule.id}", "").strip()
        body = request.form.get(f"body_{rule.id}", "").strip()
        reason = request.form.get(f"reason_{rule.id}", "").strip()
        if category and category != rule.category:
            rule.category = category
            db.session.add(rule)
        if body and body != rule.current_body:
            _apply_rule_change(rule, body, reason)

    new_category = request.form.get("new_category", "").strip()
    new_body = request.form.get("new_body", "").strip()
    if new_category and new_body:
        _create_rule(club_id, new_category, new_body, request.form.get("new_reason", "").strip())

    db.session.commit()
    return redirect(url_for("info.rules_faq"))


@info_bp.route("/rules/<int:rule_id>/history")
@require_login_guardian
def rule_history(rule_id: int):
    rule = _get_rule_or_404(rule_id)
    versions = (
        RuleVersion.query.filter_by(rule_id=rule.id).order_by(RuleVersion.changed_at.desc()).all()
    )
    return render_template("rule_history.html", rule=rule, versions=versions)


@info_bp.route("/faq", methods=["GET"])
@require_login_guardian
def faq_search():
    """FAQのキーワード検索専用ページ（一覧・追加・編集は /rules-faq に統合）。"""
    keyword = request.args.get("q", "").strip()
    query = FAQ.query.filter_by(club_id=session["club_id"])
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            db.or_(
                FAQ.question.like(pattern),
                FAQ.answer.like(pattern),
                FAQ.keywords.like(pattern),
            )
        )
    faqs = query.order_by(FAQ.category, FAQ.id).all()
    return render_template("faq.html", faqs=faqs, keyword=keyword)


@info_bp.route("/faq/bulk", methods=["POST"])
@require_admin_level("編集")
def faq_bulk_save():
    """FAQを一覧上でまとめて更新・削除・新規追加する（物品管理と同じ一括保存方式）。"""
    club_id = session["club_id"]
    for faq in FAQ.query.filter_by(club_id=club_id).all():
        if request.form.get(f"delete_{faq.id}"):
            db.session.delete(faq)
            continue
        question = request.form.get(f"question_{faq.id}", "").strip()
        answer = request.form.get(f"answer_{faq.id}", "").strip()
        if question:
            faq.question = question
        if answer:
            faq.answer = answer
        faq.category = request.form.get(f"category_{faq.id}", "").strip()
        faq.keywords = request.form.get(f"keywords_{faq.id}", "").strip()
        db.session.add(faq)

    new_question = request.form.get("new_question", "").strip()
    new_answer = request.form.get("new_answer", "").strip()
    if new_question and new_answer:
        db.session.add(
            FAQ(
                club_id=club_id,
                question=new_question,
                answer=new_answer,
                category=request.form.get("new_category", "").strip(),
                keywords=request.form.get("new_keywords", "").strip(),
            )
        )

    db.session.commit()
    return redirect(url_for("info.rules_faq"))


def _save_announcement(form: AnnouncementForm, announcement_id: Optional[int]) -> None:
    """announcement_id が指定されていれば既存を更新し、なければ新規作成する。"""
    club_id = session["club_id"]
    announcement = None
    if announcement_id is not None:
        announcement = Announcement.query.get_or_404(announcement_id)
        if announcement.club_id != club_id:
            abort(404)

    if announcement is None:
        announcement = Announcement(club_id=club_id, posted_by=current_user.id)
        db.session.add(announcement)

    announcement.title = form.title.data
    announcement.body = form.body.data
    db.session.commit()


def _create_rule(club_id: int, category: str, body: str, reason: str) -> None:
    rule = Rule(club_id=club_id, category=category.strip(), current_body=body.strip())
    db.session.add(rule)
    db.session.flush()
    db.session.add(
        RuleVersion(
            rule_id=rule.id, before="", after=rule.current_body, reason=reason, changed_by=current_user.id
        )
    )
    log_action(club_id, current_user.id, "rule_updated", "Rule", rule.id)
    db.session.commit()


def _apply_rule_change(rule: Rule, body: str, reason: str) -> None:
    before_body = rule.current_body
    rule.current_body = body
    db.session.add(rule)
    db.session.add(
        RuleVersion(
            rule_id=rule.id, before=before_body, after=body, reason=reason, changed_by=current_user.id
        )
    )
    log_action(rule.club_id, current_user.id, "rule_updated", "Rule", rule.id)


def _group_by_category(objects: List, empty_label: str = "未分類") -> List[tuple]:
    """ルール・FAQなど、category属性を持つオブジェクトをカテゴリごとにまとめる。
    呼び出し側で category, id 順に並べたクエリ結果を渡すこと（グループ内の順序もそれに従う）。
    カテゴリ名は前後の空白差で別グループにならないよう、比較前に strip() する。
    """
    grouped: dict = {}
    order: List[str] = []
    for obj in objects:
        label = (obj.category or empty_label).strip() or empty_label
        if label not in grouped:
            grouped[label] = []
            order.append(label)
        grouped[label].append(obj)
    return [(label, grouped[label]) for label in order]


def _get_rule_or_404(rule_id: int) -> Rule:
    rule = Rule.query.get_or_404(rule_id)
    if rule.club_id != session["club_id"]:
        abort(404)
    return rule
