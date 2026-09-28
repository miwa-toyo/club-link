from conftest import join_as_general_guardian, register_club


def test_admin_can_post_announcement_and_it_appears_on_today(client):
    register_club(client)
    client.post("/announcements", data={"title": "お知らせテスト", "body": "本文です"})

    response = client.get("/today")
    assert "お知らせテスト".encode() in response.data


def test_admin_can_edit_existing_announcement(client):
    """お知らせは投稿だけでなく、既存のものを編集できる。"""
    register_club(client)
    client.post("/announcements", data={"title": "元のタイトル", "body": "元の本文"})

    app = client.application
    with app.app_context():
        from clublink.models import Announcement

        announcement_id = Announcement.query.filter_by(title="元のタイトル").first().id

    client.post(
        "/announcements",
        data={"announcement_id": str(announcement_id), "title": "更新後タイトル", "body": "更新後本文"},
    )

    response = client.get("/announcements")
    assert "更新後タイトル".encode() in response.data
    assert "元のタイトル".encode() not in response.data


def test_admin_can_delete_announcement(client):
    register_club(client)
    client.post("/announcements", data={"title": "削除予定", "body": "本文"})

    app = client.application
    with app.app_context():
        from clublink.models import Announcement

        announcement_id = Announcement.query.filter_by(title="削除予定").first().id

    client.post(f"/announcements/{announcement_id}/delete")
    response = client.get("/announcements")
    assert "削除予定".encode() not in response.data


def test_schedule_list_has_no_add_button_for_general_view(client):
    """予定一覧（一般画面）には追加ボタンを置かず、管理者ホーム経由にする。"""
    register_club(client)
    response = client.get("/schedules")
    assert "予定を追加".encode() not in response.data


def test_admin_home_links_to_schedule_announcement_and_rules_faq_editing(client):
    """管理者ホームから予定追加・お知らせ編集・ルールFAQ編集に到達できる。"""
    register_club(client)
    response = client.get("/admin")
    assert "予定を追加".encode() in response.data
    assert "お知らせの編集".encode() in response.data
    assert "ルール・FAQの編集".encode() in response.data


def _get_rule_id(app, category):
    with app.app_context():
        from clublink.models import Rule

        return Rule.query.filter_by(category=category).first().id


def test_rule_bulk_save_creates_new_rule_via_new_row(client):
    """一覧下部の新規行にカテゴリ・本文を入力して一括保存すると、ルールが追加される。
    同じカテゴリで複数件登録した場合、一般保護者向け表示では見出しが1回だけになる。
    """
    register_club(client)
    client.post("/rules/bulk", data={"new_category": "持ち物", "new_body": "水筒を持参してください"})
    client.post("/rules/bulk", data={"new_category": "持ち物", "new_body": "タオルも持参してください"})

    response = client.get("/rules-faq")
    assert "水筒を持参してください".encode() in response.data
    assert "タオルも持参してください".encode() in response.data
    # 一般保護者向け表示では「持ち物」の見出しは1回だけ表示され、その下に2件がまとめられる
    assert response.data.count("【持ち物】".encode()) == 1


def test_rule_category_filter_narrows_the_list(client):
    """カテゴリで絞り込み検索ができる。"""
    register_club(client)
    client.post("/rules/bulk", data={"new_category": "持ち物", "new_body": "水筒を持参してください"})
    client.post("/rules/bulk", data={"new_category": "練習", "new_body": "土曜9時から行います"})

    response = client.get("/rules-faq?category=持ち物")
    assert "水筒を持参してください".encode() in response.data
    assert "土曜9時から行います".encode() not in response.data


def test_rule_keyword_search_matches_category_and_body(client):
    """ルールもFAQと同様、キーワードで検索できる（カテゴリ名・本文が対象）。"""
    register_club(client)
    client.post("/rules/bulk", data={"new_category": "持ち物", "new_body": "水筒を持参してください"})
    client.post("/rules/bulk", data={"new_category": "練習", "new_body": "土曜9時から行います"})

    response = client.get("/rules-faq?q=水筒")
    assert "水筒を持参してください".encode() in response.data
    assert "土曜9時から行います".encode() not in response.data

    # カテゴリ名でも検索できる
    response = client.get("/rules-faq?q=練習")
    assert "土曜9時から行います".encode() in response.data
    assert "水筒を持参してください".encode() not in response.data


def test_rule_bulk_save_updates_existing_row_and_creates_history(client):
    """既存行の本文を書き換えて一括保存すると更新され、変更履歴に記録される。"""
    register_club(client)
    client.post("/rules/bulk", data={"new_category": "服装", "new_body": "初版の本文"})
    rule_id = _get_rule_id(client.application, "服装")

    client.post(
        "/rules/bulk",
        data={f"category_{rule_id}": "服装", f"body_{rule_id}": "改訂版の本文", f"reason_{rule_id}": "見直し"},
    )

    response = client.get(f"/rules/{rule_id}/history")
    assert "初版の本文".encode() in response.data
    assert "改訂版の本文".encode() in response.data


def test_rule_bulk_save_deletes_checked_row(client):
    """削除チェックを入れて一括保存すると、そのルールが削除される。"""
    register_club(client)
    client.post("/rules/bulk", data={"new_category": "服装", "new_body": "本文"})
    rule_id = _get_rule_id(client.application, "服装")

    client.post("/rules/bulk", data={f"delete_{rule_id}": "on"})
    response = client.get("/rules-faq")
    assert "服装".encode() not in response.data


def test_faq_search_filters_by_keyword(client):
    register_club(client)
    client.post(
        "/faq/bulk",
        data={
            "new_question": "駐車場はどこですか",
            "new_answer": "体育館裏です",
            "new_keywords": "駐車場",
        },
    )
    client.post(
        "/faq/bulk",
        data={
            "new_question": "部費はいくらですか",
            "new_answer": "月3000円です",
            "new_keywords": "部費",
        },
    )

    response = client.get("/faq?q=駐車場")
    assert "駐車場はどこですか".encode() in response.data
    assert "部費はいくらですか".encode() not in response.data


def test_faq_bulk_save_creates_new_faq_via_new_row(client):
    """FAQも一覧下部の新規行から一括保存で追加できる。"""
    register_club(client)
    client.post(
        "/faq/bulk", data={"new_question": "見学Q", "new_answer": "見学A", "new_category": "入会"}
    )

    response = client.get("/rules-faq")
    assert "見学Q".encode() in response.data
    assert "【入会】".encode() in response.data


def test_faq_bulk_save_updates_and_deletes_existing_row(client):
    register_club(client)
    client.post(
        "/faq/bulk", data={"new_question": "元の質問", "new_answer": "元の回答", "new_category": "入会"}
    )
    app = client.application
    with app.app_context():
        from clublink.models import FAQ

        faq_id = FAQ.query.filter_by(question="元の質問").first().id

    client.post(
        "/faq/bulk",
        data={
            f"question_{faq_id}": "更新後の質問",
            f"answer_{faq_id}": "更新後の回答",
            f"category_{faq_id}": "入会",
        },
    )
    response = client.get("/rules-faq")
    assert "更新後の質問".encode() in response.data
    assert "元の質問".encode() not in response.data

    client.post("/faq/bulk", data={f"delete_{faq_id}": "on"})
    response = client.get("/rules-faq")
    assert "更新後の質問".encode() not in response.data


def test_admin_home_shows_invite_code_for_multi_admin_management(client):
    """管理者ホームで招待コードを確認でき、複数人での管理につなげられる。"""
    register_club(client)

    app = client.application
    with app.app_context():
        from clublink.models import Club

        invite_code = Club.query.filter_by(name="テストクラブ").first().invite_code

    response = client.get("/admin")
    assert invite_code.encode() in response.data


def test_global_preview_shows_general_guardian_view_of_rules_faq(client):
    """全項目共通のプレビュー機能で、ルール・FAQも一般保護者向けの読み取り専用表示になる。"""
    register_club(client)
    client.post("/rules/bulk", data={"new_category": "服装", "new_body": "本文"})
    client.post(
        "/faq/bulk", data={"new_question": "見学Q", "new_answer": "見学A", "new_category": "入会"}
    )

    client.post("/admin/preview/start")
    response = client.get("/rules-faq")
    assert "プレビューモード中".encode() in response.data
    assert "服装".encode() in response.data
    assert "見学Q".encode() in response.data
    # プレビュー中は編集不可（一括保存フォームが出ない）
    assert "ルールを一括保存する".encode() not in response.data
    assert "FAQを一括保存する".encode() not in response.data


def test_general_guardian_cannot_bulk_save_rules(client):
    """一般保護者は一括保存エンドポイントを実行できない（管理者限定）。"""
    register_club(client)
    client.get("/logout")
    join_as_general_guardian(client, client.application)

    response = client.post("/rules/bulk", data={"new_category": "服装", "new_body": "本文"})
    assert response.status_code == 403


def test_general_guardian_cannot_start_preview(client):
    """一般保護者はそもそもプレビュー開始ボタンを実行できない（管理者限定）。"""
    register_club(client)
    client.get("/logout")
    join_as_general_guardian(client, client.application)

    response = client.post("/admin/preview/start")
    assert response.status_code == 403


def test_support_page_is_hidden_from_general_guardian(client):
    """お問い合わせ窓口・よくある質問は管理者ホーム限定で、一般保護者はアクセスできない。"""
    register_club(client)
    client.post("/support", data={"contact_info": "クラブ代表 山田太郎（メール: club@example.com）"})

    response = client.get("/support")
    assert "クラブ代表 山田太郎".encode() in response.data
    assert "保存する".encode() in response.data

    # navには表示されない（今日の活動画面で確認）
    response = client.get("/today")
    assert "お問い合わせ".encode() not in response.data

    client.get("/logout")
    join_as_general_guardian(client, client.application)

    response = client.get("/support")
    assert response.status_code == 403


def test_support_page_shows_system_faq(client):
    """お問い合わせページにはシステムの使い方に関するよくある質問が表示される。"""
    register_club(client)
    response = client.get("/support")
    assert "ログインできません".encode() in response.data
    assert "招待コードが分かりません".encode() in response.data


def test_general_guardian_cannot_edit_contact_info(client):
    register_club(client)
    client.get("/logout")
    join_as_general_guardian(client, client.application)

    response = client.post("/support", data={"contact_info": "不正な変更"})
    assert response.status_code == 403
