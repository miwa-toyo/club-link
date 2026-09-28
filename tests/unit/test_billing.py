import io

from conftest import register_club


def test_new_club_defaults_to_standard_plan(client):
    register_club(client)
    response = client.get("/admin/plan")
    assert "Standard".encode() in response.data


def test_plan_view_shows_single_comparison_button_with_all_plans(client):
    """契約プラン画面には、プランごとではなく1つの「プランを比較する」ボタンがあり、
    押すと全プランを横並びで比較する表が表示される。
    """
    register_club(client)
    response = client.get("/admin/plan")
    assert "プランを比較する".encode() in response.data
    # 比較表には全プラン名が列見出しとして並ぶ
    assert "無料".encode() in response.data
    assert "Standard".encode() in response.data
    assert "Pro".encode() in response.data
    # 合宿機能はStandard以上で✅、無料プランでは－になる
    assert "合宿機能".encode() in response.data
    assert "✅".encode() in response.data
    assert "－".encode() in response.data


def test_standard_plan_allows_csv_export(client):
    register_club(client)
    client.post("/accounting/fees", data={"year": "2026", "month": "10", "amount_yen_male": "3000", "amount_yen_female": "2500"})
    response = client.get("/accounting/fees/billing.csv")
    assert response.status_code == 200


def test_free_plan_blocks_csv_export(client):
    register_club(client)

    app = client.application
    with app.app_context():
        from clublink.models import Plan

        free_plan_id = Plan.query.filter_by(name="無料").first().id

    client.post("/admin/plan", data={"plan_id": str(free_plan_id)})
    client.post("/accounting/fees", data={"year": "2026", "month": "10", "amount_yen_male": "3000", "amount_yen_female": "2500"})

    response = client.get("/accounting/fees/billing.csv")
    assert response.status_code == 403


def test_free_plan_blocks_ocr_upload(client):
    register_club(client)

    app = client.application
    with app.app_context():
        from clublink.models import Plan

        free_plan_id = Plan.query.filter_by(name="無料").first().id

    client.post("/admin/plan", data={"plan_id": str(free_plan_id)})
    response = client.get("/schedules/photo")
    assert response.status_code == 403


def test_pro_plan_allows_ocr_upload_page(client):
    register_club(client)

    app = client.application
    with app.app_context():
        from clublink.models import Plan

        pro_plan_id = Plan.query.filter_by(name="Pro").first().id

    client.post("/admin/plan", data={"plan_id": str(pro_plan_id)})
    response = client.get("/schedules/photo")
    assert response.status_code == 200


def test_ocr_upload_without_tesseract_falls_back_to_empty_text(client):
    """Tesseract/pytesseract未インストール環境でも例外を出さず、空文字にフォールバックする。"""
    register_club(client)

    app = client.application
    with app.app_context():
        from clublink.models import Plan

        pro_plan_id = Plan.query.filter_by(name="Pro").first().id
    client.post("/admin/plan", data={"plan_id": str(pro_plan_id)})

    fake_image = (io.BytesIO(b"not a real image"), "test.png")
    response = client.post(
        "/schedules/photo", data={"photo": fake_image}, content_type="multipart/form-data"
    )
    assert response.status_code == 302
