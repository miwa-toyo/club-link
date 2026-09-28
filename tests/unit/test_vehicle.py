from conftest import register_club


def _register_and_create_schedule(client):
    register_club(client)
    client.post(
        "/schedules/new",
        data={
            "kind": "試合",
            "starts_at": "2026-10-05T09:00",
            "place": "第二体育館",
            "needs_car": "y",
        },
    )


def test_guardian_without_can_drive_is_forbidden_to_offer_ride(client):
    _register_and_create_schedule(client)
    response = client.post("/schedules/1/vehicle", data={"direction": "行き"})
    assert response.status_code == 403


def test_guardian_with_can_drive_can_offer_and_cancel_ride(client):
    """乗車可能人数はマイページ登録時の値がそのまま使われ、申し出のたびの入力は不要。"""
    _register_and_create_schedule(client)
    client.post("/me/vehicle", data={"can_drive": "y", "vehicle_seats": "4"})

    client.post("/schedules/1/vehicle", data={"direction": "往復", "comment": "少し遅れます"})
    response = client.get("/schedules/1/vehicle")
    assert "往復（乗車可能 4人）".encode() in response.data
    assert "少し遅れます".encode() in response.data

    client.post("/schedules/1/vehicle/1/delete")
    response = client.get("/schedules/1/vehicle")
    assert "まだ申し出はありません".encode() in response.data


def test_admin_can_manage_parking_lots(client):
    register_club(client)
    client.post(
        "/parking",
        data={"name": "第一駐車場", "address": "体育館裏", "capacity": "20", "memo": ""},
    )

    response = client.get("/parking")
    assert "第一駐車場".encode() in response.data

    client.post("/parking/1/delete")
    response = client.get("/parking")
    assert "登録されている駐車場はありません".encode() in response.data
