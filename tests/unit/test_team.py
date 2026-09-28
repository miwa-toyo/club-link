from conftest import register_club


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


def test_default_team_exists_after_club_creation(client):
    _register_with_child(client)
    response = client.get("/teams")
    assert "全体".encode() in response.data


def test_can_create_additional_team(client):
    _register_with_child(client)
    client.post("/teams", data={"name": "Aチーム"})
    response = client.get("/teams")
    assert "Aチーム".encode() in response.data


def test_compose_assigns_child_to_chosen_team(client):
    _register_with_child(client)
    client.post("/teams", data={"name": "Aチーム"})

    response = client.get("/teams")
    assert "Aチーム".encode() in response.data

    app = client.application
    with app.app_context():
        from clublink.models import Child, Team

        child_id = Child.query.filter_by(court_name="たろう").first().id
        team_id = Team.query.filter_by(name="Aチーム").first().id

    client.post("/teams/compose", data={f"team_{child_id}": str(team_id)})
    response = client.get(f"/teams/{team_id}/members")
    assert "鈴木 たろう".encode() in response.data
