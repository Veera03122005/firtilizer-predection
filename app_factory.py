import json
import os
from pathlib import Path
from flask import Flask, render_template, jsonify, request
from werkzeug.security import generate_password_hash
from config import BaseConfig, DevConfig, TestConfig
from extensions import db, login_manager, csrf, limiter
from models import User, Prediction, ChatMessage
from services.ml_service import ml_service
from services.rag_service import rag_service
from services.dosage_service import compute_dosage


def create_app(config_class=None) -> Flask:
    app = Flask(__name__)

    if config_class is None:
        debug = os.getenv("FLASK_DEBUG", "0") in ("1", "true", "True")
        config_class = DevConfig if debug else BaseConfig

    app.config.from_object(config_class)

    # Fail fast if SECRET_KEY is missing in non-debug mode
    if not app.config.get("SECRET_KEY") and not app.config.get("FLASK_DEBUG") and not app.config.get("TESTING"):
        raise RuntimeError("SECRET_KEY environment variable is required in production/non-debug mode.")

    # Ensure SQLite database directory exists
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if db_uri and db_uri.startswith("sqlite:///"):
        sqlite_file = db_uri.replace("sqlite:///", "", 1)
        if sqlite_file and sqlite_file != ":memory:":
            db_file_path = Path(sqlite_file)
            db_file_path.parent.mkdir(parents=True, exist_ok=True)
    instance_path = Path(app.instance_path)
    instance_path.mkdir(parents=True, exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"
    login_manager.session_protection = "strong"

    csrf.init_app(app)
    limiter.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from blueprints.core import core_bp
    from blueprints.auth import auth_bp
    from blueprints.api import api_bp

    app.register_blueprint(core_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)

    # Auto-create tables and seed demo account on startup if needed
    with app.app_context():
        try:
            db.create_all()
            demo_user = User.query.filter_by(email="demo@example.com").first()
            if not demo_user:
                demo_user = User(
                    name="Demo Farmer",
                    email="demo@example.com",
                    password_hash=generate_password_hash("Demo@1234"),
                    preferred_language="en",
                    is_active=True,
                )
                db.session.add(demo_user)
                db.session.commit()
        except Exception as e:
            app.logger.warning(f"Could not auto-create database tables: {e}")

    # Register error handlers
    @app.errorhandler(400)
    def bad_request(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": {"code": "VALIDATION_ERROR", "message": str(e)}}), 400
        return render_template("errors/404.html"), 400

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": {"code": "NOT_FOUND", "message": "Resource not found"}}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": {"code": "RATE_LIMITED", "message": "Too many requests. Please try again later."}}), 429
        from flask import flash, redirect
        flash("Rate limit reached. Please wait a minute before trying again.", "warning")
        return redirect(request.referrer or request.url), 302

    @app.errorhandler(500)
    def internal_error(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}), 500
        return render_template("errors/500.html"), 500

    @app.errorhandler(503)
    def service_unavailable(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": {"code": "MODEL_UNAVAILABLE", "message": str(e)}}), 503
        return render_template("errors/500.html"), 503

    # CLI commands
    @app.cli.command("init-db")
    def init_db():
        """Creates all database tables."""
        instance_path = Path(app.instance_path)
        instance_path.mkdir(parents=True, exist_ok=True)
        with app.app_context():
            db.create_all()
            print(f"Initialized database tables in {app.config['SQLALCHEMY_DATABASE_URI']}")

    @app.cli.command("seed-demo")
    def seed_demo():
        """Seeds the demo user (demo@example.com / Demo@1234) and sample predictions."""
        with app.app_context():
            db.create_all()
            demo_user = User.query.filter_by(email="demo@example.com").first()
            if not demo_user:
                demo_user = User(
                    name="Demo Farmer",
                    email="demo@example.com",
                    password_hash=generate_password_hash("Demo@1234"),
                    preferred_language="en",
                    is_active=True,
                )
                db.session.add(demo_user)
                db.session.commit()
                print("Created demo user: demo@example.com / Demo@1234")

            # Seed 2 sample predictions if none exist
            if Prediction.query.filter_by(user_id=demo_user.id).count() == 0:
                p1_dosage = compute_dosage("Wheat", "DAP", 2.0, "acre", {"N": "Medium", "P": "Medium", "K": "Medium"})
                p1 = Prediction(
                    user_id=demo_user.id,
                    location="Ludhiana, Punjab",
                    weather_source="manual",
                    temperature=28.0,
                    humidity=55.0,
                    moisture=45.0,
                    soil_type="Loamy",
                    crop_type="Wheat",
                    nitrogen=12,
                    phosphorous=36,
                    potassium=0,
                    rating_n="Medium",
                    rating_p="Medium",
                    rating_k="Medium",
                    area_value=2.0,
                    area_unit="acre",
                    fertilizer="DAP",
                    confidence=0.92,
                    top3_json='[{"label":"DAP","p":0.92},{"label":"28-28","p":0.05},{"label":"Urea","p":0.03}]',
                    ood_fields_json="[]",
                    dosage_json=json.dumps(p1_dosage, ensure_ascii=False),
                    total_cost=p1_dosage.get("total_cost"),
                    price_as_of=p1_dosage.get("price_as_of"),
                    model_version=ml_service.meta.get("model_version", "2026.11.06-rf300"),
                )
                db.session.add(p1)

                p2_dosage = compute_dosage("Paddy", "Urea", 3.0, "acre", {"N": "Medium", "P": "Medium", "K": "Medium"})
                p2 = Prediction(
                    user_id=demo_user.id,
                    location="Guntur, Andhra Pradesh",
                    weather_source="open-meteo",
                    temperature=32.0,
                    humidity=68.0,
                    moisture=50.0,
                    soil_type="Clayey",
                    crop_type="Paddy",
                    nitrogen=35,
                    phosphorous=0,
                    potassium=0,
                    rating_n="Medium",
                    rating_p="Medium",
                    rating_k="Medium",
                    area_value=3.0,
                    area_unit="acre",
                    fertilizer="Urea",
                    confidence=0.89,
                    top3_json='[{"label":"Urea","p":0.89},{"label":"28-28","p":0.06},{"label":"20-20","p":0.04}]',
                    ood_fields_json="[]",
                    dosage_json=json.dumps(p2_dosage, ensure_ascii=False),
                    total_cost=p2_dosage.get("total_cost"),
                    price_as_of=p2_dosage.get("price_as_of"),
                    model_version=ml_service.meta.get("model_version", "2026.11.06-rf300"),
                )
                db.session.add(p2)
                db.session.commit()
                print("Seeded 2 sample predictions for demo user.")

    return app
