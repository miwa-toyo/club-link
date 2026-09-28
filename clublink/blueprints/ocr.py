import os

from flask import Blueprint, abort, current_app, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from clublink.extensions import db
from clublink.features import has_feature
from clublink.forms import SchedulePhotoForm
from clublink.models import SchedulePhoto
from clublink.security import require_admin_level

ocr_bp = Blueprint("ocr", __name__)

RECENT_PHOTO_LIMIT = 10


@ocr_bp.route("/schedules/photo", methods=["GET", "POST"])
@require_admin_level("編集")
def schedule_photo_upload():
    """予定表の写真をアップロードしOCRでテキスト化する任意機能（Proプラン限定）。

    OCR結果はあくまで参考情報。抽出精度は保証されないため、実際の予定作成は
    管理者が抽出テキストを見ながら手動で行う運用とする（リスクR1対策）。
    """
    club_id = session["club_id"]
    if not has_feature(club_id, "ocr"):
        abort(403)

    form = SchedulePhotoForm()
    if form.validate_on_submit():
        photo = _save_and_run_ocr(club_id, form)
        return redirect(url_for("ocr.schedule_photo_upload", photo_id=photo.id))

    photo_id = request.args.get("photo_id", type=int)
    photo = SchedulePhoto.query.get(photo_id) if photo_id else None
    if photo is not None and photo.club_id != club_id:
        abort(404)

    photos = (
        SchedulePhoto.query.filter_by(club_id=club_id)
        .order_by(SchedulePhoto.id.desc())
        .limit(RECENT_PHOTO_LIMIT)
        .all()
    )
    return render_template("schedule_photo_upload.html", form=form, photo=photo, photos=photos)


def _save_and_run_ocr(club_id: int, form: SchedulePhotoForm) -> SchedulePhoto:
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)

    file_storage = form.photo.data
    filename = secure_filename(file_storage.filename)
    save_path = os.path.join(upload_folder, filename)
    file_storage.save(save_path)

    ocr_text = _run_ocr(save_path)
    photo = SchedulePhoto(
        club_id=club_id, path=save_path, ocr_text=ocr_text, ocr_parsed=bool(ocr_text)
    )
    db.session.add(photo)
    db.session.commit()
    return photo


def _run_ocr(path: str) -> str:
    """pytesseract/Pillow か Tesseract 本体が未インストールの環境では空文字を返し、
    呼び出し側は手動編集にフォールバックする（R1対策）。この関数はネットワーク遮断
    環境のため実行検証ができていない — 実運用前に必ず動作確認すること。
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""

    try:
        return pytesseract.image_to_string(Image.open(path), lang="jpn")
    except Exception:
        return ""
