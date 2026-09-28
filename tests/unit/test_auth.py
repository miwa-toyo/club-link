from conftest import register_club


def _register(client, email="yamada@example.com", password="password123"):
    return register_club(client, email=email, password=password)


def test_index_shows_entry_points(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "ログイン".encode() in response.data


def test_register_then_login_succeeds(client):
    _register(client)
    client.get("/logout")

    response = client.post(
        "/login",
        data={"email": "yamada@example.com", "password": "password123"},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/onboarding") is False


def test_login_with_wrong_password_is_rejected(client):
    _register(client, email="sato@example.com")
    client.get("/logout")

    response = client.post(
        "/login",
        data={"email": "sato@example.com", "password": "wrong-password"},
        follow_redirects=True,
    )
    assert "メールアドレスまたはパスワードが違います".encode() in response.data


def test_cross_club_session_is_rejected(client):
    """他クラブの club_id をセッションに入れても 403 になる（R4: マルチテナント境界対策）。"""
    _register(client)
    with client.session_transaction() as session:
        session["club_id"] = 999999

    response = client.get("/today")
    assert response.status_code == 403


def test_duplicate_email_registration_is_rejected(client):
    _register(client, email="dup@example.com")
    client.get("/logout")

    response = _register(client, email="dup@example.com")
    assert "既に登録されています".encode() in response.data


def test_onboarding_registers_first_child_and_vehicle_info(client):
    """初回アンケートで最初のお子さまと送迎情報を登録できる。"""
    _register(client)
    client.post(
        "/onboarding",
        data={
            "family_name": "山田",
            "court_name": "いちろう",
            "birth_date": "2015-04-01",
            "gender": "男子",
            "allergy": "卵",
            "can_drive": "y",
            "vehicle_seats": "4",
        },
    )

    response = client.get("/me")
    assert "山田 いちろう".encode() in response.data
    assert "送迎: 可".encode() in response.data
    assert "乗車可能人数: 4".encode() in response.data
