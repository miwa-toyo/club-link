from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    BooleanField,
    DateField,
    DateTimeLocalField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
)
from wtforms.validators import DataRequired, Email, Length, NumberRange

from clublink.models.camp import EXPENSE_KINDS
from clublink.models.family import CHILD_GENDERS
from clublink.models.schedule import SCHEDULE_KINDS
from clublink.models.user import ADMIN_LEVELS
from clublink.models.vehicle import DIRECTIONS

MIN_PASSWORD_LENGTH = 8
MIN_MONTH, MAX_MONTH = 1, 12


class LoginForm(FlaskForm):
    email = StringField("メールアドレス", validators=[DataRequired(), Email()])
    password = PasswordField("パスワード", validators=[DataRequired()])


class RegisterForm(FlaskForm):
    club_name = StringField("クラブ名", validators=[DataRequired(), Length(max=100)])
    display_name = StringField("お名前", validators=[DataRequired(), Length(max=100)])
    email = StringField("メールアドレス", validators=[DataRequired(), Email()])
    password = PasswordField(
        "パスワード", validators=[DataRequired(), Length(min=MIN_PASSWORD_LENGTH)]
    )


class JoinForm(FlaskForm):
    invite_code = StringField("招待コード", validators=[DataRequired()])
    display_name = StringField("お名前", validators=[DataRequired(), Length(max=100)])
    email = StringField("メールアドレス", validators=[DataRequired(), Email()])
    password = PasswordField(
        "パスワード", validators=[DataRequired(), Length(min=MIN_PASSWORD_LENGTH)]
    )


class OnboardingForm(FlaskForm):
    family_name = StringField("苗字", validators=[DataRequired(), Length(max=50)])
    court_name = StringField("お子さまのコートネーム", validators=[DataRequired(), Length(max=50)])
    birth_date = DateField(
        "誕生日", validators=[DataRequired()], render_kw={"type": "date"}
    )
    gender = SelectField(
        "性別区分（チーム分け・部費計算に使用）",
        choices=[(g, g) for g in CHILD_GENDERS],
        validators=[DataRequired()],
    )
    allergy = StringField("アレルギー", render_kw={"placeholder": "例: 卵、そば（なければ空欄でOK）"})
    can_drive = BooleanField("送迎できる車がある")
    vehicle_seats = IntegerField(
        "乗車可能人数（車がある場合）", validators=[NumberRange(min=0)], default=0
    )


class ChildForm(FlaskForm):
    family_name = StringField("苗字", validators=[DataRequired(), Length(max=50)])
    court_name = StringField("コートネーム", validators=[DataRequired(), Length(max=50)])
    birth_date = DateField(
        "生年月日", validators=[DataRequired()], render_kw={"type": "date"}
    )
    gender = SelectField(
        "性別区分（チーム分け・部費計算に使用）",
        choices=[(g, g) for g in CHILD_GENDERS],
        validators=[DataRequired()],
    )
    allergy = StringField("アレルギー", render_kw={"placeholder": "例: 卵、そば（なければ空欄でOK）"})
    status = SelectField(
        "状態",
        choices=[("active", "在籍"), ("graduated", "卒団"), ("withdrawn", "退部")],
        validators=[DataRequired()],
    )


class VehicleForm(FlaskForm):
    can_drive = BooleanField("送迎できます")
    vehicle_seats = IntegerField("乗車可能人数", validators=[NumberRange(min=0)])


class ScheduleForm(FlaskForm):
    kind = SelectField(
        "種別", choices=[(k, k) for k in SCHEDULE_KINDS], validators=[DataRequired()]
    )
    starts_at = DateTimeLocalField(
        "開始日時", format="%Y-%m-%dT%H:%M", validators=[DataRequired()]
    )
    place = StringField("場所")
    needs_car = BooleanField("送迎が必要")


class AbsenceReportForm(FlaskForm):
    """CSRFトークンのみを扱うフォーム。予定×子供ごとの欠席チェック・理由は動的フィールド名で受け取る。"""

    pass


class AnnouncementForm(FlaskForm):
    title = StringField("タイトル", validators=[DataRequired(), Length(max=200)])
    body = StringField(
        "本文", validators=[DataRequired()], render_kw={"placeholder": "例: 来週の練習は雨天のため中止です"}
    )


class VehicleAssignmentForm(FlaskForm):
    direction = SelectField(
        "行き/帰り/往復", choices=[(d, d) for d in DIRECTIONS], validators=[DataRequired()]
    )
    comment = StringField(
        "コメント（任意）", render_kw={"placeholder": "伝えたいことがあれば入力してください"}
    )


class ParkingLotForm(FlaskForm):
    name = StringField("駐車場名", validators=[DataRequired(), Length(max=100)])
    address = StringField("住所")
    capacity = IntegerField("収容台数", validators=[NumberRange(min=0)], default=0)
    memo = StringField("メモ")


class FeeForm(FlaskForm):
    year = IntegerField("年度", validators=[DataRequired()])
    month = IntegerField(
        "月", validators=[DataRequired(), NumberRange(min=MIN_MONTH, max=MAX_MONTH)]
    )
    amount_yen_male = IntegerField(
        "男子の月額（円）", validators=[DataRequired(), NumberRange(min=0)]
    )
    amount_yen_female = IntegerField(
        "女子の月額（円）", validators=[DataRequired(), NumberRange(min=0)]
    )



class CampForm(FlaskForm):
    title = StringField("合宿名", validators=[DataRequired(), Length(max=100)])
    starts_on = DateField("開始日", validators=[DataRequired()], render_kw={"type": "date"})
    ends_on = DateField("終了日", validators=[DataRequired()], render_kw={"type": "date"})
    place_text = StringField("場所")


class CampFeeGridForm(FlaskForm):
    """CSRFトークンのみを扱うフォーム。保護者ごとの金額は動的フィールド名で受け取る。"""

    pass


class PackingGridForm(FlaskForm):
    """CSRFトークンのみを扱うフォーム。持ち物の名称・必要数は動的フィールド名で受け取る。"""

    pass


class CampExpenseGridForm(FlaskForm):
    """CSRFトークンのみを扱うフォーム。支出の種別・金額・メモ・削除フラグは動的フィールド名で受け取る。"""

    pass


class CampExpenseForm(FlaskForm):
    kind = SelectField(
        "種別", choices=[(k, k) for k in EXPENSE_KINDS], validators=[DataRequired()]
    )
    amount_yen = IntegerField("金額（円）", validators=[DataRequired(), NumberRange(min=0)])
    memo = StringField("メモ", render_kw={"placeholder": "例: 夕食の食材費"})


class PackingItemForm(FlaskForm):
    name = StringField(
        "持ち物", validators=[DataRequired(), Length(max=100)], render_kw={"placeholder": "例: 水筒"}
    )
    target_count = IntegerField("必要数", validators=[NumberRange(min=0)], default=1)


class TeamForm(FlaskForm):
    name = StringField("チーム名", validators=[DataRequired(), Length(max=50)])


class AdminRoleForm(FlaskForm):
    guardian_id = IntegerField("保護者ID", validators=[DataRequired()])
    name = StringField("役職名", validators=[DataRequired(), Length(max=50)])
    level = SelectField(
        "権限レベル", choices=[(lvl, lvl) for lvl in ADMIN_LEVELS], validators=[DataRequired()]
    )


class ClubYearForm(FlaskForm):
    name = StringField("新しい年度名", validators=[DataRequired(), Length(max=20)])





class PlanChangeForm(FlaskForm):
    plan_id = SelectField("プラン", coerce=int, validators=[DataRequired()])


class SchedulePhotoForm(FlaskForm):
    photo = FileField(
        "予定表の写真",
        validators=[
            DataRequired(),
            FileAllowed(["jpg", "jpeg", "png"], "画像ファイル（jpg/png）のみアップロードできます"),
        ],
    )
