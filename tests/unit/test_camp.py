from conftest import join_as_general_guardian, register_club


def _create_camp(client):
    register_club(client)
    client.post(
        "/camps/new",
        data={
            "title": "夏合宿",
            "starts_on": "2026-08-01",
            "ends_on": "2026-08-03",
            "place_text": "白馬",
        },
    )


def _default_category_ids(client):
    """既定の4費目（バス代/宿泊費/キャンセル料/交通費）は合宿作成時にID 1〜4で生成される。"""
    return {"バス代": 1, "宿泊費": 2, "キャンセル料": 3, "交通費": 4}


def test_camp_creation_generates_fee_row_and_default_categories(client):
    _create_camp(client)
    response = client.get("/camps/1/fees")
    assert "山田太郎".encode() in response.data
    assert "バス代".encode() in response.data
    assert "宿泊費".encode() in response.data


def test_marking_camp_fee_paid_creates_accounting_entry(client):
    _create_camp(client)
    cat = _default_category_ids(client)
    client.post(
        "/camps/1/fees",
        data={
            f"amount_1_{cat['バス代']}": "3000",
            f"amount_1_{cat['宿泊費']}": "5000",
            f"amount_1_{cat['キャンセル料']}": "0",
            f"amount_1_{cat['交通費']}": "0",
            "status_1": "支払い済み",
        },
    )

    response = client.get("/accounting/allocations")
    assert "合宿費".encode() in response.data
    assert "8000円".encode() in response.data


def test_category_label_can_be_freely_renamed(client):
    """費目名は固定ではなく自由に書き換えられる。"""
    _create_camp(client)
    cat = _default_category_ids(client)
    client.post(
        "/camps/1/fees",
        data={
            f"category_label_{cat['キャンセル料']}": "保険料",
            f"amount_1_{cat['バス代']}": "0",
            f"amount_1_{cat['宿泊費']}": "0",
            f"amount_1_{cat['キャンセル料']}": "0",
            f"amount_1_{cat['交通費']}": "0",
            "status_1": "未払い",
        },
    )

    response = client.get("/camps/1/fees")
    assert "保険料".encode() in response.data
    assert "キャンセル料".encode() not in response.data


def test_new_category_can_be_added_via_grid(client):
    """一覧画面から新しい費目を自由に追加できる。"""
    _create_camp(client)
    cat = _default_category_ids(client)
    client.post(
        "/camps/1/fees",
        data={
            f"amount_1_{cat['バス代']}": "0",
            f"amount_1_{cat['宿泊費']}": "0",
            f"amount_1_{cat['キャンセル料']}": "0",
            f"amount_1_{cat['交通費']}": "0",
            "status_1": "未払い",
            "new_category_label": "お土産代",
        },
    )

    response = client.get("/camps/1/fees")
    assert "お土産代".encode() in response.data


def test_camp_detail_hides_fee_management_link_from_general_guardian(client):
    """合宿詳細の「合宿費の管理」リンクは一般保護者には表示されない（管理者限定バッジの整合性）。"""
    _create_camp(client)
    client.get("/logout")
    join_as_general_guardian(client, client.application)

    response = client.get("/camps/1")
    assert "合宿費の管理".encode() not in response.data
    assert "支出の記録".encode() in response.data


def test_camp_detail_shows_fee_management_link_to_editor(client):
    _create_camp(client)
    response = client.get("/camps/1")
    assert "合宿費の管理".encode() in response.data


def test_expense_add_creates_accounting_entry_immediately(client):
    _create_camp(client)
    client.post(
        "/camps/1/expenses",
        data={"new_kind": "食費", "new_amount": "12000", "new_memo": "夕食"},
    )

    response = client.get("/accounting/allocations")
    assert "合宿支出".encode() in response.data
    assert "12000円".encode() in response.data


def test_expense_can_be_edited_and_deleted_ledger_style(client):
    """家計簿のように既存の支出行を1画面で更新・削除できる。"""
    _create_camp(client)
    client.post(
        "/camps/1/expenses",
        data={"new_kind": "食費", "new_amount": "12000", "new_memo": "夕食"},
    )

    client.post(
        "/camps/1/expenses",
        data={"kind_1": "補食", "amount_1": "9000", "memo_1": "夕食（訂正）"},
    )
    response = client.get("/accounting/allocations")
    assert "9000円".encode() in response.data
    assert "12000円".encode() not in response.data

    client.post("/camps/1/expenses", data={"delete_1": "on"})
    response = client.get("/accounting/allocations")
    assert "会計記録はまだありません".encode() in response.data


def test_settle_calc_shows_balance(client):
    _create_camp(client)
    cat = _default_category_ids(client)
    client.post(
        "/camps/1/fees",
        data={
            f"amount_1_{cat['バス代']}": "3000",
            f"amount_1_{cat['宿泊費']}": "5000",
            f"amount_1_{cat['キャンセル料']}": "0",
            f"amount_1_{cat['交通費']}": "0",
            "status_1": "支払い済み",
        },
    )
    client.post(
        "/camps/1/expenses",
        data={"new_kind": "食費", "new_amount": "2000", "new_memo": "昼食"},
    )

    response = client.get("/camps/1/settle")
    assert "8000円".encode() in response.data
    assert "2000円".encode() in response.data
    assert "6000円".encode() in response.data


def test_packing_item_with_zero_target_is_hidden(client):
    _create_camp(client)
    client.post("/camps/1/packing", data={"new_name": "水筒", "new_count": "0"})
    client.post("/camps/1/packing", data={"new_name": "タオル", "new_count": "2"})

    response = client.get("/camps/1/packing")
    assert "タオル".encode() in response.data
    assert "水筒".encode() not in response.data


def test_packing_item_can_be_bulk_edited(client):
    """持ち物リストは一度に一括編集できる。"""
    _create_camp(client)
    client.post("/camps/1/packing", data={"new_name": "水筒", "new_count": "1"})

    client.post("/camps/1/packing", data={"name_1": "水筒（大）", "count_1": "2"})
    response = client.get("/camps/1/packing")
    assert "水筒（大）".encode() in response.data
