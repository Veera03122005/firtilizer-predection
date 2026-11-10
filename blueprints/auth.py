from urllib.parse import urlparse
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, limiter
from forms import LoginForm, RegisterForm
from models import User

auth_bp = Blueprint("auth", __name__)


def is_safe_url(target: str) -> bool:
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(target)
    return test_url.scheme in ("", "http", "https") and ref_url.netloc == test_url.netloc or target.startswith("/") and not target.startswith("//")


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("core.dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        existing = User.query.filter_by(email=email).first()
        if existing:
            form.email.errors.append("An account with this email already exists.")
            flash("An account with this email already exists. Please log in.", "warning")
            return render_template("auth/register.html", form=form)

        user = User(
            name=form.name.data.strip(),
            email=email,
            password_hash=generate_password_hash(form.password.data),
            preferred_language=form.preferred_language.data,
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash("Registration successful! Welcome to Smart Fertilizer Advisor.", "success")
        return redirect(url_for("core.dashboard"))

    elif request.method == "POST" and form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                field_label = form[field].label.text if field in form else field
                flash(f"{field_label}: {error}", "danger")

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("core.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, form.password.data):
            if not user.is_active:
                flash("This account has been deactivated.", "danger")
                return render_template("auth/login.html", form=form)

            login_user(user, remember=form.remember.data)
            user.last_login_at = datetime.now(timezone.utc)
            db.session.commit()

            next_page = request.args.get("next")
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for("core.dashboard"))
        else:
            flash("Email or password is incorrect", "danger")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for("core.index"))

