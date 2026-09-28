from conftest import register_club, seed_sample_data


def test_mypage_shows_no_children_on_fresh_club(client):
    """新規クラブには子供がまだ登録されていない。"""
    register_club(client)
    response = client.get("/me")
    assert response.status_code == 200
    assert "登録されているお子さまはいません".encode() in response.data


def test_mypage_shows_sample_children_after_seeding(client):
    """サンプルデータ投入後は、男女それぞれの子供が表示される。"""
    register_club(client)
    seed_sample_data(client)

    response = client.get("/me")
    assert "サンプル 大輝".encode() in response.data
    assert "サンプル さくら".encode() in response.data


def test_add_child_appears_on_mypage(client):
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
    response = client.get("/me")
    assert "鈴木 たろう".encode() in response.data


def test_vehicle_edit_updates_guardian(client):
    register_club(client)
    client.post("/me/vehicle", data={"can_drive": "y", "vehicle_seats": "4"})
    response = client.get("/me")
    assert "送迎: 可".encode() in response.data
    assert "乗車可能人数: 4".encode() in response.data


def test_cannot_edit_another_clubs_child(client):
    """他クラブの子供IDを直接叩いても404になることを確認する。"""
    register_club(client)
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

    response = client.get("/me/family/1")
    assert response.status_code == 404
