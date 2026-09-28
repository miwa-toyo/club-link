from conftest import join_as_general_guardian, register_club


def test_admin_can_add_edit_and_delete_inventory_item_in_bulk(client):
    """物品は一覧上でまとめて新規追加・更新・削除できる。"""
    register_club(client)
    client.post("/inventory", data={"new_name": "ゼッケン", "new_count": "20", "new_location": "倉庫"})

    response = client.get("/inventory")
    assert "ゼッケン".encode() in response.data

    client.post(
        "/inventory",
        data={"name_1": "ゼッケン（更新）", "count_1": "15", "location_1": "倉庫2階"},
    )
    response = client.get("/inventory")
    assert "ゼッケン（更新）".encode() in response.data

    client.post("/inventory", data={"delete_1": "on"})
    response = client.get("/inventory")
    assert "登録されている備品はありません".encode() in response.data


def test_non_editor_cannot_post_inventory_item(client):
    register_club(client)
    client.get("/logout")
    join_as_general_guardian(client, client.application)

    response = client.post(
        "/inventory", data={"new_name": "不正登録", "new_count": "1", "new_location": ""}
    )
    assert response.status_code == 403


def test_inventory_category_is_saved_correctly(client):
    """物品にはカテゴリ（保護者用/子供用）を設定でき、カテゴリ見出し（「用」を省いた表記）でグループ表示される。"""
    register_club(client)
    client.post(
        "/inventory",
        data={"new_name": "受付名簿", "new_count": "1", "new_location": "事務局", "new_category": "保護者用"},
    )
    client.post(
        "/inventory",
        data={"new_name": "ゼッケン", "new_count": "20", "new_location": "倉庫", "new_category": "子供用"},
    )

    response = client.get("/rules-faq")
    assert "【保護者】".encode() in response.data
    assert "【子供】".encode() in response.data
    assert "受付名簿：1個（事務局）".encode() in response.data
    assert "ゼッケン：20個（倉庫）".encode() in response.data


def test_general_guardian_can_see_inventory_from_rules_faq_page(client):
    """一般保護者は物品管理ページには入れないが、ルール・FAQページから物品をカテゴリ別に閲覧できる。"""
    register_club(client)
    client.post(
        "/inventory",
        data={"new_name": "ゼッケン", "new_count": "20", "new_location": "倉庫", "new_category": "子供用"},
    )

    client.get("/logout")
    join_as_general_guardian(client, client.application)

    response = client.get("/rules-faq")
    assert "ゼッケン".encode() in response.data
    assert "【子供】".encode() in response.data
