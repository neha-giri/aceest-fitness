import pytest

from app import calculate_calories, create_app


@pytest.fixture
def client(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})
    with app.test_client() as c:
        yield c


def add(client, name="Arun", **extra):
    return client.post("/clients", json={"name": name, **extra})


# ---------- general ----------
def test_home(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.get_json()["status"] == "running"


def test_health(client):
    assert client.get("/health").get_json() == {"status": "healthy"}


# ---------- login ----------
def test_login_success(client):
    r = client.post("/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200
    assert r.get_json()["role"] == "Admin"


def test_login_failure(client):
    r = client.post("/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401
    assert client.post("/login", json={}).status_code == 401


# ---------- programs & calories ----------
def test_programs(client):
    assert set(client.get("/programs").get_json()) == {"Fat Loss", "Muscle Gain", "Beginner"}


@pytest.mark.parametrize("weight,ptype,expected",
                         [(70, "Fat Loss", 1540), (70, "Muscle Gain", 2450),
                          (70, "Beginner", 1820)])
def test_calculate_calories(weight, ptype, expected):
    assert calculate_calories(weight, ptype) == expected


def test_calculate_calories_invalid():
    with pytest.raises(ValueError):
        calculate_calories(-1, "Fat Loss")
    with pytest.raises(ValueError):
        calculate_calories(70, "Unknown")


def test_calories_endpoint(client):
    r = client.post("/calories", json={"weight": 80, "program_type": "Muscle Gain"})
    assert r.get_json()["calories"] == 2800
    assert client.post("/calories", json={"weight": "x"}).status_code == 400


# ---------- clients ----------
def test_add_and_get_client(client):
    r = add(client, age=25, weight=70, height=175)
    assert r.status_code == 201
    assert r.get_json()["membership_status"] == "Active"
    assert client.get("/clients/Arun").get_json()["age"] == 25
    assert client.get("/clients").get_json() == ["Arun"]


def test_add_client_validation(client):
    assert add(client, name="").status_code == 400
    assert add(client, age="old").status_code == 400
    assert add(client, membership_status="Gold").status_code == 400
    assert add(client, membership_end="31-12-2026").status_code == 400


def test_duplicate_client(client):
    add(client)
    assert add(client).status_code == 409


def test_client_not_found(client):
    assert client.get("/clients/Ghost").status_code == 404
    assert client.put("/clients/Ghost", json={"age": 1}).status_code == 404
    assert client.delete("/clients/Ghost").status_code == 404


def test_update_client(client):
    add(client)
    r = client.put("/clients/Arun", json={"weight": 72.5, "calories": 2000})
    assert r.status_code == 200
    assert r.get_json()["weight"] == 72.5
    assert client.put("/clients/Arun", json={}).status_code == 400
    assert client.put("/clients/Arun", json={"age": "x"}).status_code == 400
    assert client.put("/clients/Arun", json={"membership_status": "Bad"}).status_code == 400


def test_delete_client(client):
    add(client)
    client.post("/clients/Arun/workouts", json={"workout_type": "Cardio"})
    assert client.delete("/clients/Arun").status_code == 200
    assert client.get("/clients/Arun").status_code == 404


# ---------- program generator ----------
def test_generate_program_random(client):
    add(client)
    r = client.post("/clients/Arun/generate-program")
    assert r.status_code == 200
    saved = client.get("/clients/Arun").get_json()["program"]
    assert saved == r.get_json()["program"]


def test_generate_program_specific(client):
    add(client)
    r = client.post("/clients/Arun/generate-program", json={"program_type": "Beginner"})
    assert r.get_json()["program"] in ["Full Body 3x/week", "Light Strength + Mobility"]
    bad = client.post("/clients/Arun/generate-program", json={"program_type": "X"})
    assert bad.status_code == 400
    assert client.post("/clients/Ghost/generate-program").status_code == 404


# ---------- membership ----------
def test_membership(client):
    add(client, membership_end="2026-12-31")
    assert client.get("/clients/Arun/membership").get_json() == {
        "membership": "Active", "renewal_date": "2026-12-31"}
    add(client, name="Bob")
    assert client.get("/clients/Bob/membership").get_json()["renewal_date"] == "N/A"
    assert client.get("/clients/Ghost/membership").status_code == 404


# ---------- progress ----------
def test_progress(client):
    add(client)
    assert client.post("/clients/Arun/progress",
                       json={"week": "Week 1", "adherence": 80}).status_code == 201
    client.post("/clients/Arun/progress", json={"week": "Week 2", "adherence": 90})
    data = client.get("/clients/Arun/progress").get_json()
    assert [d["adherence"] for d in data] == [80, 90]


def test_progress_validation(client):
    add(client)
    assert client.post("/clients/Arun/progress",
                       json={"week": "W1", "adherence": 150}).status_code == 400
    assert client.post("/clients/Arun/progress",
                       json={"week": "W1", "adherence": "x"}).status_code == 400
    assert client.post("/clients/Arun/progress",
                       json={"week": "", "adherence": 50}).status_code == 400
    assert client.get("/clients/Ghost/progress").status_code == 404


# ---------- workouts ----------
def test_workouts(client):
    add(client)
    r = client.post("/clients/Arun/workouts",
                    json={"date": "2026-01-01", "workout_type": "Strength",
                          "duration_min": 45, "notes": "leg day"})
    assert r.status_code == 201
    client.post("/clients/Arun/workouts",
                json={"date": "2026-02-01", "workout_type": "Cardio"})
    data = client.get("/clients/Arun/workouts").get_json()
    assert data[0]["date"] == "2026-02-01"          # newest first
    assert data[0]["duration_min"] == 60            # default
    assert len(data) == 2


def test_workout_validation(client):
    add(client)
    url = "/clients/Arun/workouts"
    assert client.post(url, json={"workout_type": "Yoga"}).status_code == 400
    assert client.post(url, json={"workout_type": "Cardio", "date": "bad"}).status_code == 400
    assert client.post(url, json={"workout_type": "Cardio",
                                  "duration_min": 0}).status_code == 400
    assert client.post(url, json={"workout_type": "Cardio",
                                  "duration_min": "x"}).status_code == 400
    assert client.get("/clients/Ghost/workouts").status_code == 404


# ---------- metrics ----------
def test_metrics(client):
    add(client)
    r = client.post("/clients/Arun/metrics",
                    json={"date": "2026-01-01", "weight": 70, "waist": 80, "bodyfat": 18})
    assert r.status_code == 201
    assert client.get("/clients/Arun/metrics").get_json()[0]["bodyfat"] == 18
    assert client.post("/clients/Arun/metrics", json={"weight": "x"}).status_code == 400
    assert client.post("/clients/Arun/metrics",
                       json={"weight": 70, "date": "bad"}).status_code == 400
    assert client.get("/clients/Ghost/metrics").status_code == 404


# ---------- report ----------
def test_report(client):
    add(client, weight=70)
    client.post("/clients/Arun/progress", json={"week": "W1", "adherence": 80})
    client.post("/clients/Arun/progress", json={"week": "W2", "adherence": 91})
    client.post("/clients/Arun/workouts", json={"workout_type": "Strength"})
    rep = client.get("/clients/Arun/report").get_json()
    assert rep["average_adherence"] == 85.5
    assert rep["total_workouts"] == 1
    assert rep["client"]["name"] == "Arun"


def test_report_empty_and_missing(client):
    add(client)
    assert client.get("/clients/Arun/report").get_json()["average_adherence"] is None
    assert client.get("/clients/Ghost/report").status_code == 404
