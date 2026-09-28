from datetime import datetime

from clublink.extensions import db


class Announcement(db.Model):
    """お知らせ。team_id が NULL の場合はクラブ全体向け。"""

    __tablename__ = "announcements"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    posted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    posted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)


class Rule(db.Model):
    """ルール。カテゴリはタグとして扱い、同じカテゴリで複数件登録できる。"""

    __tablename__ = "rules"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False, index=True)
    current_body = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class RuleVersion(db.Model):
    """ルール変更履歴。1回の更新につき1行。"""

    __tablename__ = "rule_versions"

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey("rules.id"), nullable=False, index=True)
    before = db.Column(db.Text, nullable=False)
    after = db.Column(db.Text, nullable=False)
    reason = db.Column(db.String(255), default="", nullable=False)
    changed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class FAQ(db.Model):
    """よくある質問。keywords はカンマ区切りの検索補助語。"""

    __tablename__ = "faqs"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False, index=True)
    question = db.Column(db.String(255), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default="", nullable=False)
    keywords = db.Column(db.String(255), default="", nullable=False)
