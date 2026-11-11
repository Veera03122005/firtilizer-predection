import tempfile
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import BaseConfig
from app_factory import create_app
from models import User

def test_fresh_deployment():
    # Simulate fresh Render container filesystem
    tmp = Path(tempfile.mkdtemp())
    fresh_db = tmp / "instance" / "render_test.db"

    class FreshRenderConfig(BaseConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{fresh_db}"
        SECRET_KEY = "render-test-secret"
        TESTING = True
        WTF_CSRF_ENABLED = False

    # 1. Startup app
    app = create_app(FreshRenderConfig)
    client = app.test_client()

    with app.app_context():
        # Verify tables exist
        demo = User.query.filter_by(email="demo@example.com").first()
        assert demo is not None, "Demo user should be auto-created on fresh startup"
        print("PASS: Fresh startup auto-created database and demo user:", demo.email)

    # 2. Test registration of a brand new user on fresh deployment
    res = client.post("/register", data={
        "name": "New Render Farmer",
        "email": "render_farmer@gmail.com",
        "preferred_language": "en",
        "password": "Password@1234",
        "confirm_password": "Password@1234",
    }, follow_redirects=True)

    assert res.status_code == 200, f"Registration failed with status {res.status_code}"
    print("PASS: POST /register succeeded on fresh deployment!")

    with app.app_context():
        new_user = User.query.filter_by(email="render_farmer@gmail.com").first()
        assert new_user is not None, "New user was not saved in DB!"
        print("PASS: Verified user saved in database:", new_user.email, new_user.name)

    shutil.rmtree(tmp, ignore_errors=True)
    print("\nALL RENDER SIMULATION CHECKS PASSED!")

if __name__ == "__main__":
    test_fresh_deployment()
