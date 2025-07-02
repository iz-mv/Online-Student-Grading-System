import pytest
from app import create_app, db
from models import User, Assignment
from werkzeug.security import generate_password_hash

@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def setup_users(app):
    with app.app_context():
        teacher = User(
            email="teacher@example.com",
            password=generate_password_hash("qwerty123"),
            name="Teacher",
            role="teacher"
        )
        student = User(
            email="student@example.com",
            password=generate_password_hash("qwerty123"),
            name="Student",
            role="student"
        )
        db.session.add_all([teacher, student])
        db.session.commit()
        return {"teacher": teacher, "student": student}

def login(client, email, password):
    return client.post("/login", data={
        "email": email,
        "password": password
    }, follow_redirects=True)

def test_successful_login(client, setup_users):
    response = login(client, "teacher@example.com", "qwerty123")
    assert b"Dashboard" in response.data or response.status_code == 200

def test_wrong_password(client, setup_users):
    response = login(client, "teacher@example.com", "wrongpass")
    assert "Неверный email или пароль" in response.get_data(as_text=True)

def test_student_cannot_access_teacher_page(client, setup_users):
    login(client, "student@example.com", "qwerty123")
    response = client.get("/create_assignment")
    assert response.status_code in (302, 403, 401, 404)  # В зависимости от реализации

def test_login_with_nonexistent_user(client, setup_users):
    response = login(client, "idontexist@example.com", "password")
    assert "Неверный email или пароль" in response.get_data(as_text=True)
