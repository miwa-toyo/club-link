from datetime import date

from clublink.extensions import db

CHILD_STATUSES = ("active", "graduated", "withdrawn")
CHILD_STATUS_LABELS = {"active": "在籍", "graduated": "卒団", "withdrawn": "退部"}
CHILD_GENDERS = ("男子", "女子")

# Guardian(保護者) と Child(子) は多対多（1子に複数保護者、1保護者に複数子を許容）。
guardian_children = db.Table(
    "guardian_children",
    db.Column("guardian_id", db.Integer, db.ForeignKey("guardians.id"), primary_key=True),
    db.Column("child_id", db.Integer, db.ForeignKey("children.id"), primary_key=True),
)


class Child(db.Model):
    """クラブに所属する子供。個人情報保護のため本名でなく苗字+コートネームのみ保存する（R5対策）。

    status が graduated/withdrawn の場合、left_club_year_id にその年度（ClubYear）を
    記録することで、年度ごとのOB/OG（卒団・退部者）管理ができるようにしている。
    """

    __tablename__ = "children"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False, index=True)
    family_name = db.Column(db.String(50), nullable=False)
    court_name = db.Column(db.String(50), nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    joined_at = db.Column(db.Date, default=date.today, nullable=False)
    allergy = db.Column(db.String(255), default="", nullable=False)
    status = db.Column(db.String(20), default="active", nullable=False)
    gender = db.Column(db.String(10), default="男子", nullable=False)
    left_club_year_id = db.Column(db.Integer, db.ForeignKey("club_years.id"), nullable=True)

    guardians = db.relationship(
        "Guardian", secondary=guardian_children, back_populates="children"
    )

    @property
    def display_name(self) -> str:
        return f"{self.family_name} {self.court_name}"

    @property
    def status_label(self) -> str:
        return CHILD_STATUS_LABELS.get(self.status, self.status)
