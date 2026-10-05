# ACEest Fitness & Gym - DevOps CI/CD Project

Flask web service for gym management, converted from the original **ACEest Tkinter desktop
application** (latest version 3.2.4), with a complete CI/CD pipeline using Git/GitHub,
Pytest, Docker, GitHub Actions and Jenkins.

## Project Structure
```
app.py                      Flask application (API)
test_app.py                 Pytest unit tests
requirements.txt            Python dependencies
Dockerfile                  Container image definition
Jenkinsfile                 Jenkins pipeline (BUILD / quality gate)
.github/workflows/main.yml  GitHub Actions CI pipeline
legacy_versions/            Original Tkinter versions 1.0 -> 3.2.4 (kept for history)
```

## Features (ported from v3.2.4)
Login (admin/admin by default), client management, AI-style program generator, membership
check, weekly adherence progress, workouts, body metrics, calorie estimation and client report.

## API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/`, `/health` | Status / health check |
| POST | `/login` | `{"username","password"}` |
| GET | `/programs` | Program templates |
| POST | `/calories` | `{"weight":70,"program_type":"Fat Loss"}` |
| GET / POST | `/clients` | List / add client |
| GET / PUT / DELETE | `/clients/<name>` | Get / update / delete client |
| POST | `/clients/<name>/generate-program` | Generate program (optional `program_type`) |
| GET | `/clients/<name>/membership` | Membership status and renewal date |
| GET / POST | `/clients/<name>/progress` | Weekly adherence |
| GET / POST | `/clients/<name>/workouts` | Workouts |
| GET / POST | `/clients/<name>/metrics` | Weight, waist, body fat |
| GET | `/clients/<name>/report` | Client report (replaces PDF report) |

## Local Setup
```bash
git clone https://github.com/neha-giri/aceest-fitness.git
cd aceest-fitness
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py                   # http://localhost:5000
```

## Run Tests Manually
```bash
pytest -v
flake8 .
```

## Docker
```bash
docker build -t aceest-fitness .
docker run -p 5000:5000 aceest-fitness
docker run --rm aceest-fitness pytest -v     # run tests inside the container
```
The image uses `python:3.12-slim`, `--no-cache-dir`, a layer-cached dependency install and a
non-root user.

## CI/CD Overview
**GitHub Actions** (`.github/workflows/main.yml`) runs on every push and pull request:
1. **Build & Lint** - install dependencies, syntax check (`py_compile`), `flake8`.
2. **Docker Build & Test** - build the image and run `pytest` inside the container.

**Jenkins** (`Jenkinsfile`) is the secondary BUILD / quality gate. It pulls the latest code
from GitHub, creates a clean virtualenv, installs dependencies, compiles, runs the tests and
builds the Docker image.

## Branching & Commits
`main` is stable. Work is done on `feature/*`, `bugfix/*` and `infra/*` branches and merged
through pull requests. Commits use prefixes: `feat`, `test`, `infra`, `ci`, `docs`.
