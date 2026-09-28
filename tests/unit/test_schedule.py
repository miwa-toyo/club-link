from conftest import register_club, seed_sample_data


def _register_with_child(client):
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


def _create_schedule(client):
    client.post(
        "/schedules/new",
        data={
            "kind": "練習",
            "starts_at": "2026-10-01T18:00",
            "place": "第一体育館",
            "needs_car": "y",
        },
    )


def test_today_dashboard_shows_sample_content_after_seeding(client):
    """サンプルデータ投入後は、今日の活動にお知らせ・予定が表示される。"""
    register_club(client)
    seed_sample_data(client)

    response = client.get("/today")
    assert response.status_code == 200
    assert "来週の練習について".encode() in response.data


def test_admin_can_create_schedule_and_it_appears_in_list(client):
    _register_with_child(client)
    _create_schedule(client)

    response = client.get("/schedules")
    assert "練習".encode() in response.data
    assert "第一体育館".encode() in response.data


def test_guardian_can_report_absence_from_mypage(client):
    """欠席連絡はマイページから行い、管理者の予定詳細画面に反映される。"""
    _register_with_child(client)
    _create_schedule(client)

    app = client.application
    with app.app_context():
        from datetime import datetime

        from clublink.models import Child, Schedule

        schedule_id = Schedule.query.filter_by(starts_at=datetime(2026, 10, 1, 18, 0)).first().id
        child_id = Child.query.filter_by(court_name="たろう").first().id

    client.post(
        f"/me/absences/{schedule_id}",
        data={f"absent_{schedule_id}_{child_id}": "on", f"reason_{schedule_id}_{child_id}": "体調不良"},
    )

    response = client.get(f"/schedules/{schedule_id}")
    assert "鈴木 たろう".encode() in response.data
    assert "体調不良".encode() in response.data


def test_schedule_detail_shows_all_attend_when_no_absence_reported(client):
    """欠席連絡が無ければ、管理者画面には「全員参加予定」と表示される。"""
    _register_with_child(client)
    _create_schedule(client)

    response = client.get("/schedules/1")
    assert "欠席の連絡はありません（全員参加予定です）".encode() in response.data


def test_unchecking_absence_removes_the_report(client):
    """チェックを外して保存すると、欠席連絡が取り消される（参加扱いに戻る）。"""
    _register_with_child(client)
    _create_schedule(client)

    app = client.application
    with app.app_context():
        from datetime import datetime

        from clublink.models import Child, Schedule

        schedule_id = Schedule.query.filter_by(starts_at=datetime(2026, 10, 1, 18, 0)).first().id
        child_id = Child.query.filter_by(court_name="たろう").first().id

    client.post(f"/me/absences/{schedule_id}", data={f"absent_{schedule_id}_{child_id}": "on"})
    client.post(f"/me/absences/{schedule_id}", data={})

    response = client.get(f"/schedules/{schedule_id}")
    assert "欠席の連絡はありません（全員参加予定です）".encode() in response.data


def test_admin_home_shows_recent_absence_as_notification(client):
    """欠席連絡は管理者ホームに「最近の欠席連絡」として通知代わりに表示される。"""
    _register_with_child(client)
    _create_schedule(client)

    app = client.application
    with app.app_context():
        from datetime import datetime

        from clublink.models import Child, Schedule

        schedule_id = Schedule.query.filter_by(starts_at=datetime(2026, 10, 1, 18, 0)).first().id
        child_id = Child.query.filter_by(court_name="たろう").first().id

    client.post(
        f"/me/absences/{schedule_id}",
        data={f"absent_{schedule_id}_{child_id}": "on", f"reason_{schedule_id}_{child_id}": "体調不良"},
    )

    response = client.get("/admin")
    assert "鈴木 たろう".encode() in response.data
    assert "体調不良".encode() in response.data


def test_cannot_view_schedule_of_another_club(client):
    _register_with_child(client)
    _create_schedule(client)
    client.get("/logout")

    client.post(
        "/register",
        data={
            "club_name": "別クラブ",
            "display_name": "佐藤次郎",
            "email": "jiro@example.com",
            "password": "password123",
        },
    )

    response = client.get("/schedules/1")
    assert response.status_code == 404
