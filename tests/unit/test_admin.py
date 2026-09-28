from conftest import join_as_general_guardian, register_club


def test_removing_sole_important_admin_is_rejected(client):
    """重要管理者が1人しかいない状態での解除は422で拒否される（R6対策・受入チェックリスト5）。"""
    register_club(client)
    response = client.post("/admin/admins", data={"guardian_id": "1", "action": "remove"})
    assert response.status_code == 422


def test_year_update_creates_new_current_year(client):
    register_club(client)
    client.post("/admin/year", data={"name": "2027年度"})

    response = client.get("/admin/year")
    assert "2027年度".encode() in response.data
    assert "（現行）".encode() in response.data


def test_year_member_bulk_update_marks_child_as_graduated_with_year(client):
    """OB/OG管理：子供を「卒団」にし、卒団した年度を設定できる。"""
    register_club(client)
    client.post(
        "/me/family",
        data={
            "family_name": "鈴木",
            "court_name": "たろう",
            "birth_date": "2010-04-01",
            "gender": "男子",
            "allergy": "",
            "status": "active",
        },
    )

    app = client.application
    with app.app_context():
        from clublink.models import Child, ClubYear

        child_id = Child.query.filter_by(court_name="たろう").first().id
        year_id = ClubYear.query.first().id

    client.post(
        "/admin/year/members",
        data={f"status_{child_id}": "graduated", f"left_year_{child_id}": str(year_id)},
    )

    response = client.get("/admin/year")
    assert "鈴木 たろう（卒団）".encode() in response.data


def test_year_member_bulk_update_supports_withdrawn_status(client):
    """在籍状態には「退部」も選べる。"""
    register_club(client)
    client.post(
        "/me/family",
        data={
            "family_name": "田中",
            "court_name": "はな",
            "birth_date": "2011-04-01",
            "gender": "女子",
            "allergy": "",
            "status": "active",
        },
    )

    app = client.application
    with app.app_context():
        from clublink.models import Child, ClubYear

        child_id = Child.query.filter_by(court_name="はな").first().id
        year_id = ClubYear.query.first().id

    client.post(
        "/admin/year/members",
        data={f"status_{child_id}": "withdrawn", f"left_year_{child_id}": str(year_id)},
    )

    response = client.get("/admin/year")
    assert "田中 はな（退部）".encode() in response.data


def test_setting_status_back_to_active_clears_left_year(client):
    """在籍に戻すと、卒団・退部した年度の記録はクリアされる。"""
    register_club(client)
    client.post(
        "/me/family",
        data={
            "family_name": "鈴木",
            "court_name": "たろう",
            "birth_date": "2010-04-01",
            "gender": "男子",
            "allergy": "",
            "status": "active",
        },
    )
    app = client.application
    with app.app_context():
        from clublink.models import Child, ClubYear

        child_id = Child.query.filter_by(court_name="たろう").first().id
        year_id = ClubYear.query.first().id

    client.post(
        "/admin/year/members",
        data={f"status_{child_id}": "graduated", f"left_year_{child_id}": str(year_id)},
    )
    client.post("/admin/year/members", data={f"status_{child_id}": "active"})

    app = client.application
    with app.app_context():
        from clublink.models import Child

        child = Child.query.get(child_id)
        assert child.status == "active"
        assert child.left_club_year_id is None


def test_rule_update_is_recorded_in_audit_log(client):
    register_club(client)
    client.post("/rules/bulk", data={"new_category": "服装", "new_body": "本文", "new_reason": "初回"})

    response = client.get("/admin/audit")
    assert "rule_updated".encode() in response.data


def test_non_admin_guardian_is_forbidden_from_admin_home(client):
    """招待コード経由で参加した一般保護者は管理者権限を持たず、/admin へのアクセスは403になる。"""
    register_club(client)
    client.get("/logout")
    join_as_general_guardian(client, client.application)

    response = client.get("/admin")
    assert response.status_code == 403


def test_general_guardian_nav_shows_only_minimum_items(client):
    """一般保護者のナビには、今日の活動・予定・お知らせ・ルールFAQ・マイページ・ログアウトのみ表示し、
    管理者ホームは表示しない（管理保護者との完全分離）。
    """
    register_club(client)
    client.get("/logout")
    join_as_general_guardian(client, client.application)

    response = client.get("/today")
    assert "今日の活動".encode() in response.data
    assert "お知らせ".encode() in response.data
    assert "ルール・FAQ".encode() in response.data
    assert "マイページ".encode() in response.data
    assert "管理者ホーム".encode() not in response.data


def test_admin_guardian_nav_shows_only_admin_home_link(client):
    """管理保護者（編集権限以上）のナビには、個別の運営系項目（会計・合宿・物品等）は並べず、
    「管理者ホーム」1つだけを表示する（そこから各機能に辿る）。
    """
    register_club(client)
    response = client.get("/today")
    assert "管理者ホーム".encode() in response.data


def test_preview_mode_hides_admin_nav_and_blocks_admin_routes(client):
    """プレビュー中は管理者本人でも一般保護者と同じ画面になり、管理者限定ルートは403になる。"""
    register_club(client)
    client.post("/admin/preview/start")

    response = client.get("/today")
    assert "管理者ホーム".encode() not in response.data


    response = client.get("/admin")
    assert response.status_code == 403


def test_preview_mode_can_be_stopped(client):
    register_club(client)
    client.post("/admin/preview/start")
    client.post("/admin/preview/stop")

    response = client.get("/today")
    assert "管理者ホーム".encode() in response.data


def test_admin_list_search_filters_by_name(client):
    """管理者一覧は保護者名で検索できる。"""
    register_club(client)
    client.get("/logout")
    join_as_general_guardian(client, client.application)
    client.get("/logout")
    client.post(
        "/login", data={"email": "yamada@example.com", "password": "password123"}
    )

    response = client.get("/admin/admins?q=花子")
    assert "一般 花子".encode() in response.data
    assert "山田太郎".encode() not in response.data


def test_audit_log_filters_by_action(client):
    """監査ログは操作種別で絞り込める（絞り込みのドロップダウン自体には全種別が並ぶため、
    表の行数で絞り込み効果を確認する）。
    """
    register_club(client)
    client.post("/rules/bulk", data={"new_category": "服装", "new_body": "本文", "new_reason": "初回"})
    client.post("/admin/year", data={"name": "2027年度"})

    unfiltered = client.get("/admin/audit")
    filtered = client.get("/admin/audit?action=year_updated")

    assert filtered.data.count(b"<tr>") < unfiltered.data.count(b"<tr>")
    assert "year_updated".encode() in filtered.data


def test_seed_sample_data_populates_club(client):
    """サンプルデータ投入で、お知らせ・予定・子供などがまとめて登録される。"""
    register_club(client)
    client.post("/admin/sample-data")

    response = client.get("/today")
    assert "来週の練習について".encode() in response.data

    response = client.get("/me")
    assert "サンプル 大輝".encode() in response.data


def test_delete_sample_data_removes_only_sample_content(client):
    """サンプルデータは削除でき、その際に実際に追加した通常データは消えない。"""
    register_club(client)
    client.post("/admin/sample-data")
    client.post("/announcements", data={"title": "本物のお知らせ", "body": "これは残ってほしい"})
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

    client.post("/admin/sample-data/delete")

    response = client.get("/today")
    assert "来週の練習について".encode() not in response.data
    assert "本物のお知らせ".encode() in response.data

    response = client.get("/me")
    assert "サンプル 大輝".encode() not in response.data
    assert "鈴木 たろう".encode() in response.data

    response = client.get("/rules-faq")
    assert "持ち物は何がありますか？".encode() not in response.data


def test_important_admin_can_reset_a_guardians_password(client):
    """重要管理者は保護者のパスワードを再設定でき、新しい仮パスワードでログインできるようになる。"""
    register_club(client)
    client.get("/logout")
    join_as_general_guardian(client, client.application)
    client.get("/logout")
    client.post("/login", data={"email": "yamada@example.com", "password": "password123"})

    app = client.application
    with app.app_context():
        from clublink.models import Guardian

        guardian_id = Guardian.query.filter_by(display_name="一般 花子").first().id

    response = client.post(f"/admin/admins/{guardian_id}/reset-password", follow_redirects=True)
    assert "新しいパスワード".encode() in response.data

    # 表示された新パスワードを画面から取り出してログインし直せることを確認
    import re

    match = re.search(r"新しいパスワード：([^\s（]+)", response.data.decode("utf-8"))
    assert match is not None
    new_password = match.group(1)

    client.get("/logout")
    response = client.post(
        "/login", data={"email": "hanako@example.com", "password": new_password}
    )
    assert response.status_code == 302

    # 旧パスワードではログインできなくなっている
    client.get("/logout")
    response = client.post(
        "/login", data={"email": "hanako@example.com", "password": "password123"}, follow_redirects=True
    )
    assert "メールアドレスまたはパスワードが違います".encode() in response.data


def test_non_important_admin_cannot_reset_password(client):
    """重要管理者以外はパスワードを再設定できない。"""
    register_club(client)
    client.get("/logout")
    join_as_general_guardian(client, client.application)

    app = client.application
    with app.app_context():
        from clublink.models import Guardian

        guardian_id = Guardian.query.filter_by(display_name="一般 花子").first().id

    response = client.post(f"/admin/admins/{guardian_id}/reset-password")
    assert response.status_code == 403
