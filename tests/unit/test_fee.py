from conftest import register_club


def _setup_fee(client):
    """新規クラブで、男子の子供1人分の部費を作成する。"""
    register_club(client)
    client.post(
        "/me/family",
        data={
            "family_name": "鈴木",
            "court_name": "たろう",
            "birth_date": "2015-04-01",
            "gender": "男子",
            "allergy": "",
            "status": "active",
        },
    )
    client.post(
        "/accounting/fees",
        data={"year": "2026", "month": "10", "amount_yen_male": "3000", "amount_yen_female": "2500"},
    )


def test_fee_creation_generates_payment_for_owner_guardian(client):
    _setup_fee(client)
    response = client.get("/accounting/fees/1/payments")
    assert "山田太郎".encode() in response.data
    assert "未納".encode() in response.data


def test_marking_paid_creates_accounting_entry_once(client):
    _setup_fee(client)
    client.post("/accounting/fees/1/payments", data={"status_1": "入金済み"})

    response = client.get("/accounting/allocations")
    assert response.data.count("部費".encode()) == 1
    assert "3000円".encode() in response.data


def test_reverting_payment_removes_accounting_entry(client):
    _setup_fee(client)
    client.post("/accounting/fees/1/payments", data={"status_1": "入金済み"})
    client.post("/accounting/fees/1/payments", data={"status_1": "未納"})

    response = client.get("/accounting/allocations")
    assert "会計記録はまだありません".encode() in response.data


def test_billing_csv_contains_club_id_in_filename(client):
    _setup_fee(client)
    response = client.get("/accounting/fees/billing.csv")
    assert response.status_code == 200
    assert "billing_club1.csv" in response.headers["Content-Disposition"]


def test_payment_status_filter_shows_only_matching_rows(client):
    """入金状況一覧は状態で絞り込める。"""
    _setup_fee(client)
    client.post(
        "/me/family",
        data={
            "family_name": "田中",
            "court_name": "はな",
            "birth_date": "2016-05-01",
            "gender": "女子",
            "allergy": "",
            "status": "active",
        },
    )
    client.post("/accounting/fees/1/payments", data={"status_1": "入金済み"})

    response = client.get("/accounting/fees/1/payments?status=入金済み")
    assert "山田太郎".encode() in response.data


def test_payment_filter_does_not_reset_hidden_rows_on_save(client):
    """絞り込みで非表示の行は、更新ボタンを押しても状態が変わらない（安全性）。"""
    _setup_fee(client)
    client.post("/accounting/fees/1/payments", data={"status_1": "入金済み"})

    # 「未納のみ」で絞り込んだ状態で保存しても、既に入金済みの行は変更されない
    client.post("/accounting/fees/1/payments?status=未納", data={})

    response = client.get("/accounting/allocations")
    assert "3000円".encode() in response.data


def test_monthly_carryover_accumulates_across_months(client):
    """月をまたぐと、前月の残高が翌月の繰越金として引き継がれる。"""
    register_club(client)
    client.post(
        "/accounting/allocations",
        data={"new_kind": "収入", "new_amount": "5000", "new_memo": "1月分寄付"},
    )
    client.post(
        "/accounting/allocations",
        data={"new_kind": "支出", "new_amount": "2000", "new_memo": "2月分備品"},
    )

    app = client.application
    with app.app_context():
        from datetime import datetime

        from clublink.extensions import db
        from clublink.models import AccountingEntry

        income_entry = AccountingEntry.query.filter_by(memo="1月分寄付").first()
        income_entry.created_at = datetime(2026, 1, 15)
        expense_entry = AccountingEntry.query.filter_by(memo="2月分備品").first()
        expense_entry.created_at = datetime(2026, 2, 15)
        db.session.commit()

    response = client.get("/accounting/allocations")
    assert "2026年1月".encode() in response.data
    assert "2026年2月".encode() in response.data
    # 2月の繰越金（前月から）は、1月の残高5000円がそのまま引き継がれる
    assert "5000円".encode() in response.data
    # 2月の残高（翌月への繰越金）は 5000 - 2000 = 3000円
    assert "3000円".encode() in response.data


def test_allocation_summary_shows_fee_total_and_expense_total(client):
    """会計画面に部費合計額・支出合計・現在の残高が表示される。"""
    _setup_fee(client)
    client.post("/accounting/fees/1/payments", data={"status_1": "入金済み"})
    client.post(
        "/accounting/allocations",
        data={"new_kind": "支出", "new_amount": "1000", "new_memo": "備品購入"},
    )

    response = client.get("/accounting/allocations")
    assert "部費合計額：3000円".encode() in response.data
    assert "支出合計：1000円".encode() in response.data
    assert "現在の残高（繰越金）：2000円".encode() in response.data


def test_manual_accounting_entry_requires_editor(client):
    register_club(client)
    response = client.post(
        "/accounting/allocations",
        data={"new_kind": "支出", "new_amount": "1000", "new_memo": "備品購入"},
    )
    assert response.status_code == 302

    response = client.get("/accounting/allocations")
    assert "備品購入".encode() in response.data


def test_manual_accounting_entries_can_be_bulk_edited_and_deleted(client):
    """手動入力の会計仕訳は一覧上でまとめて更新・削除できる。"""
    register_club(client)
    client.post(
        "/accounting/allocations",
        data={"new_kind": "支出", "new_amount": "1000", "new_memo": "備品購入"},
    )

    app = client.application
    with app.app_context():
        from clublink.models import AccountingEntry

        entry_id = AccountingEntry.query.filter_by(memo="備品購入").first().id

    client.post(
        "/accounting/allocations",
        data={f"kind_{entry_id}": "支出", f"amount_{entry_id}": "1500", f"memo_{entry_id}": "備品購入（追加分）"},
    )
    response = client.get("/accounting/allocations")
    assert "1500円".encode() in response.data
    assert "備品購入（追加分）".encode() in response.data

    client.post("/accounting/allocations", data={f"delete_{entry_id}": "on"})
    response = client.get("/accounting/allocations")
    assert "会計記録はまだありません".encode() in response.data


def test_auto_generated_accounting_entry_is_not_editable_via_bulk_form(client):
    """部費入金など自動生成された仕訳は、会計の一括編集フォームでは編集できない。"""
    register_club(client)
    client.post(
        "/me/family",
        data={
            "family_name": "鈴木",
            "court_name": "たろう",
            "birth_date": "2015-04-01",
            "gender": "男子",
            "allergy": "",
            "status": "active",
        },
    )
    client.post(
        "/accounting/fees",
        data={"year": "2026", "month": "10", "amount_yen_male": "3000", "amount_yen_female": "2500"},
    )
    client.post("/accounting/fees/1/payments", data={"status_1": "入金済み"})

    app = client.application
    with app.app_context():
        from clublink.models import AccountingEntry

        entry_id = AccountingEntry.query.filter_by(source_type="部費").first().id

    # 自動生成分のフィールド名(kind_/amount_/memo_)を送っても無視され、3000円のまま変わらない
    client.post(
        "/accounting/allocations",
        data={f"kind_{entry_id}": "支出", f"amount_{entry_id}": "9999", f"memo_{entry_id}": "改ざん"},
    )
    response = client.get("/accounting/allocations")
    assert "3000円".encode() in response.data
    assert "9999円".encode() not in response.data
