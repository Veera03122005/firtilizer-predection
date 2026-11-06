from datetime import datetime, timezone
import json
from flask_login import UserMixin
from sqlalchemy import event
from sqlalchemy.engine import Engine
from extensions import db


def utcnow():
    return datetime.now(timezone.utc)


@event.listens_for(Engine, "connect")
def _fk_on(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    preferred_language = db.Column(db.String(5), nullable=False, default="en")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    predictions = db.relationship(
        "Prediction", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )


class Prediction(db.Model):
    __tablename__ = "predictions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )
    location = db.Column(db.String(120), nullable=True)
    weather_source = db.Column(db.String(20), nullable=True, default="manual")

    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)
    moisture = db.Column(db.Float, nullable=False)
    soil_type = db.Column(db.String(20), nullable=False)
    crop_type = db.Column(db.String(30), nullable=False)
    nitrogen = db.Column(db.Integer, nullable=False)
    phosphorous = db.Column(db.Integer, nullable=False)
    potassium = db.Column(db.Integer, nullable=False)

    rating_n = db.Column(db.String(6), nullable=False, default="Medium")
    rating_p = db.Column(db.String(6), nullable=False, default="Medium")
    rating_k = db.Column(db.String(6), nullable=False, default="Medium")

    area_value = db.Column(db.Float, nullable=False, default=1.0)
    area_unit = db.Column(db.String(5), nullable=False, default="acre")

    fertilizer = db.Column(db.String(20), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    top3_json = db.Column(db.Text, nullable=False, default="[]")
    ood_fields_json = db.Column(db.Text, nullable=False, default="[]")

    dosage_json = db.Column(db.Text, nullable=True)
    total_cost = db.Column(db.Float, nullable=True)
    price_as_of = db.Column(db.String(20), nullable=True)
    model_version = db.Column(db.String(40), nullable=False)

    chats = db.relationship(
        "ChatMessage",
        backref="prediction",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    __table_args__ = (
        db.Index("ix_predictions_user_created", "user_id", "created_at"),
    )

    @property
    def top3(self):
        try:
            return json.loads(self.top3_json) if self.top3_json else []
        except Exception:
            return []

    @property
    def ood_fields(self):
        try:
            return json.loads(self.ood_fields_json) if self.ood_fields_json else []
        except Exception:
            return []

    @property
    def dosage(self):
        try:
            return json.loads(self.dosage_json) if self.dosage_json else None
        except Exception:
            return None


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    __table_args__ = (
        db.CheckConstraint("role in ('user', 'assistant')", name="ck_chat_role"),
        db.Index("ix_chat_prediction_created", "prediction_id", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prediction_id = db.Column(
        db.Integer, db.ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role = db.Column(db.String(10), nullable=False)
    content = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(5), nullable=False, default="en")
    sources_json = db.Column(db.Text, nullable=False, default="[]")
    fallback = db.Column(db.Boolean, nullable=False, default=False)
    latency_ms = db.Column(db.Integer, nullable=True)
    model = db.Column(db.String(60), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    @property
    def sources(self):
        try:
            return json.loads(self.sources_json) if self.sources_json else []
        except Exception:
            return []


class ContactMessage(db.Model):
    __tablename__ = "contact_messages"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

