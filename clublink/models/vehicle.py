from clublink.extensions import db

DIRECTIONS = ("行き", "帰り", "往復")


class VehicleAssignment(db.Model):
    """予定ごとの車出し割り当て。保護者本人が申し出て登録する自己申告制。

    乗車可能人数は初回アンケートでの登録値（Guardian.vehicle_seats）を使うため、
    申し出のたびに入力させない。ガソリン代の入力欄も設けない。
    """

    __tablename__ = "vehicle_assignments"
    __table_args__ = (
        db.UniqueConstraint(
            "schedule_id", "guardian_id", "direction", name="uq_vehicle_assignment"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("schedules.id"), nullable=False, index=True)
    guardian_id = db.Column(db.Integer, db.ForeignKey("guardians.id"), nullable=False, index=True)
    direction = db.Column(db.String(10), nullable=False)
    comment = db.Column(db.String(255), default="", nullable=False)


class ParkingLot(db.Model):
    """駐車場情報。管理者限定で登録・削除する。"""

    __tablename__ = "parking_lots"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(255), default="", nullable=False)
    capacity = db.Column(db.Integer, default=0, nullable=False)
    memo = db.Column(db.String(255), default="", nullable=False)
