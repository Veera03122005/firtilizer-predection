import time
import json
from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user
from extensions import db, limiter
from models import Prediction, ChatMessage
from services.ml_service import ml_service
from services.rag_service import rag_service
from services.weather_service import geocode, current as get_current_weather, WeatherError

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/chat", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def chat():
    data = request.get_json(silent=True) or {}
    prediction_id = data.get("prediction_id")
    question = (data.get("question") or "").strip()
    language = data.get("language", "en")

    if not prediction_id or not question:
        return jsonify({"error": {"code": "VALIDATION_ERROR", "message": "prediction_id and question are required"}}), 400

    if len(question) > 500:
        return jsonify({"error": {"code": "VALIDATION_ERROR", "message": "question exceeds 500 characters"}}), 400

    if language not in ("en", "te", "ta", "hi"):
        return jsonify({"error": {"code": "VALIDATION_ERROR", "message": "invalid language code"}}), 400

    prediction = Prediction.query.filter_by(id=prediction_id, user_id=current_user.id).first()
    if not prediction:
        return jsonify({"error": {"code": "NOT_FOUND", "message": "Prediction not found"}}), 404

    t0 = time.time()
    pred_context = {
        "crop": prediction.crop_type,
        "soil": prediction.soil_type,
        "fertilizer": prediction.fertilizer,
        "confidence": prediction.confidence,
        "nitrogen": prediction.nitrogen,
        "phosphorous": prediction.phosphorous,
        "potassium": prediction.potassium,
    }

    result = rag_service.answer(question, prediction_context=pred_context, language=language)
    latency_ms = int((time.time() - t0) * 1000)

    # Save user message
    user_msg = ChatMessage(
        user_id=current_user.id,
        prediction_id=prediction.id,
        role="user",
        content=question,
        language=language,
        sources_json="[]",
        fallback=False,
    )
    db.session.add(user_msg)

    # Save assistant message
    asst_msg = ChatMessage(
        user_id=current_user.id,
        prediction_id=prediction.id,
        role="assistant",
        content=result["answer"],
        language=language,
        sources_json=json.dumps(result.get("sources", []), ensure_ascii=False),
        fallback=result.get("fallback", False),
        latency_ms=latency_ms,
        model=result.get("model"),
    )
    db.session.add(asst_msg)
    db.session.commit()

    return jsonify({
        "answer": result["answer"],
        "sources": result.get("sources", []),
        "fallback": result.get("fallback", False),
        "latency_ms": latency_ms,
        "model": result.get("model"),
    })


@api_bp.route("/chat/<int:prediction_id>", methods=["GET"])
@login_required
def get_chat(prediction_id: int):
    prediction = Prediction.query.filter_by(id=prediction_id, user_id=current_user.id).first()
    if not prediction:
        return jsonify({"error": {"code": "NOT_FOUND", "message": "Prediction not found"}}), 404

    messages = (
        ChatMessage.query.filter_by(prediction_id=prediction.id, user_id=current_user.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    return jsonify({
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "language": m.language,
                "sources": m.sources,
                "fallback": m.fallback,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ]
    })


@api_bp.route("/weather", methods=["GET"])
@limiter.limit("30 per minute")
def weather():
    location = request.args.get("location", "").strip()
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    if not location and not (lat and lon):
        return jsonify({"error": {"code": "VALIDATION_ERROR", "message": "Provide location name or lat/lon coordinates"}}), 400

    try:
        if location:
            results = geocode(location)
            if not results:
                return jsonify({"error": {"code": "NOT_FOUND", "message": f"Location '{location}' not found"}}), 404

            best = results[0]
            w = get_current_weather(best["latitude"], best["longitude"])
            return jsonify({
                "temperature": round(w["temperature"], 1),
                "humidity": int(round(w["humidity"])),
                "matches": [
                    {
                        "name": r.get("name"),
                        "admin1": r.get("admin1"),
                        "country": r.get("country"),
                        "latitude": r.get("latitude"),
                        "longitude": r.get("longitude"),
                    }
                    for r in results[:5]
                ],
            })
        else:
            w = get_current_weather(float(lat), float(lon))
            return jsonify({
                "temperature": round(w["temperature"], 1),
                "humidity": int(round(w["humidity"])),
            })
    except WeatherError as e:
        return jsonify({"error": {"code": "UPSTREAM_ERROR", "message": str(e)}}), 502
    except Exception as e:
        return jsonify({"error": {"code": "INTERNAL_ERROR", "message": str(e)}}), 500

