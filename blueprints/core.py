from io import BytesIO
import json
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify, send_file
from flask_login import login_required, current_user
from extensions import db
from forms import PredictForm, ContactForm
from models import Prediction, ContactMessage, ChatMessage
from services.ml_service import ml_service
from services.dosage_service import compute_dosage
from services.report_service import build_pdf
from services.rag_service import rag_service
from services.llm_client import llm_client

logger = logging.getLogger(__name__)
core_bp = Blueprint("core", __name__)


def get_owned_prediction_or_404(prediction_id: int) -> Prediction:
    pred = Prediction.query.filter_by(id=prediction_id, user_id=current_user.id).first()
    if not pred:
        abort(404)
    return pred


@core_bp.route("/")
def index():
    opts = ml_service.options()
    cv_acc = 94
    if ml_service.meta and "cv" in ml_service.meta:
        cv_acc = int(round(ml_service.meta["cv"].get("accuracy_mean", 0.94) * 100))

    return render_template(
        "index.html",
        accuracy_pct=cv_acc,
        crops_count=len(opts.get("crop_types", [])),
        soils_count=len(opts.get("soil_types", [])),
    )


@core_bp.route("/about")
def about():
    return render_template("about.html", meta=ml_service.meta)


@core_bp.route("/contact", methods=["GET", "POST"])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        user_id = current_user.id if current_user.is_authenticated else None
        msg = ContactMessage(
            user_id=user_id,
            name=form.name.data.strip(),
            email=form.email.data.strip().lower(),
            message=form.message.data.strip(),
        )
        db.session.add(msg)
        db.session.commit()
        flash("Thanks, we'll get back to you.", "success")
        return redirect(url_for("core.contact"))

    return render_template("contact.html", form=form)


@core_bp.route("/dashboard")
@login_required
def dashboard():
    total_preds = Prediction.query.filter_by(user_id=current_user.id).count()
    total_chats = ChatMessage.query.filter_by(user_id=current_user.id, role="user").count()
    last_pred = (
        Prediction.query.filter_by(user_id=current_user.id)
        .order_by(Prediction.created_at.desc())
        .first()
    )
    recent_preds = (
        Prediction.query.filter_by(user_id=current_user.id)
        .order_by(Prediction.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "dashboard.html",
        total_predictions=total_preds,
        total_chats=total_chats,
        last_fertilizer=last_pred.fertilizer if last_pred else None,
        last_crop=last_pred.crop_type if last_pred else None,
        recent_predictions=recent_preds,
    )


@core_bp.route("/predictor", methods=["GET"])
@login_required
def predictor():
    form = PredictForm()
    opts = ml_service.options()
    form.soil.choices = [(s, s) for s in opts.get("soil_types", [])]
    form.crop.choices = [(c, c) for c in opts.get("crop_types", [])]

    return render_template(
        "predictor.html",
        form=form,
        model_loaded=ml_service.model_loaded,
        soil_types=opts.get("soil_types", []),
        crop_types=opts.get("crop_types", []),
    )


@core_bp.route("/predict", methods=["POST"])
@login_required
def predict():
    if not ml_service.model_loaded:
        abort(503, description="Model not trained — run python ml/train.py")

    form = PredictForm()
    opts = ml_service.options()
    form.soil.choices = [(s, s) for s in opts.get("soil_types", [])]
    form.crop.choices = [(c, c) for c in opts.get("crop_types", [])]

    if not form.validate_on_submit():
        logger.warning(f"PredictForm validation errors: {form.errors}")
        return render_template(
            "predictor.html",
            form=form,
            model_loaded=ml_service.model_loaded,
            soil_types=opts.get("soil_types", []),
            crop_types=opts.get("crop_types", []),
        ), 400

    temp = form.temperature.data
    hum = form.humidity.data
    moist = form.moisture.data
    soil = form.soil.data
    crop = form.crop.data
    n = form.nitrogen.data
    p = form.phosphorous.data
    k = form.potassium.data
    area_val = form.area_value.data or 1.0
    area_unit = form.area_unit.data or "acre"

    # ML prediction
    try:
        pred_res = ml_service.predict({
            "temperature": temp,
            "humidity": hum,
            "moisture": moist,
            "soil": soil,
            "crop": crop,
            "nitrogen": n,
            "phosphorous": p,
            "potassium": k,
        })
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        flash(f"Prediction error: {str(e)}", "danger")
        return redirect(url_for("core.predictor"))

    # Rule-based dosage calculation
    dosage_res = None
    try:
        ratings = {
            "N": form.rating_n.data or "Medium",
            "P": form.rating_p.data or "Medium",
            "K": form.rating_k.data or "Medium",
        }
        dosage_res = compute_dosage(
            crop=crop,
            fertilizer=pred_res["fertilizer"],
            area_value=area_val,
            area_unit=area_unit,
            ratings=ratings,
        )
    except Exception as e:
        logger.warning(f"Dosage computation failed for {crop}: {e}")

    # Save to database
    prediction = Prediction(
        user_id=current_user.id,
        location=form.location.data.strip() if form.location.data else None,
        weather_source=form.weather_source.data or "manual",
        temperature=temp,
        humidity=hum,
        moisture=moist,
        soil_type=soil,
        crop_type=crop,
        nitrogen=n,
        phosphorous=p,
        potassium=k,
        rating_n=form.rating_n.data or "Medium",
        rating_p=form.rating_p.data or "Medium",
        rating_k=form.rating_k.data or "Medium",
        area_value=area_val,
        area_unit=area_unit,
        fertilizer=pred_res["fertilizer"],
        confidence=pred_res["confidence"],
        top3_json=json.dumps(pred_res.get("top3", []), ensure_ascii=False),
        ood_fields_json=json.dumps(pred_res.get("ood_fields", []), ensure_ascii=False),
        dosage_json=json.dumps(dosage_res, ensure_ascii=False) if dosage_res else None,
        total_cost=dosage_res.get("total_cost") if dosage_res else None,
        price_as_of=dosage_res.get("price_as_of") if dosage_res else None,
        model_version=pred_res.get("model_version", "unknown"),
    )
    db.session.add(prediction)
    db.session.commit()

    return redirect(url_for("core.result", id=prediction.id))


@core_bp.route("/result/<int:id>")
@login_required
def result(id: int):
    prediction = get_owned_prediction_or_404(id)
    chat_messages = (
        ChatMessage.query.filter_by(prediction_id=prediction.id, user_id=current_user.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return render_template("result.html", prediction=prediction, chat_messages=chat_messages)


@core_bp.route("/history")
@login_required
def history():
    page = request.args.get("page", 1, type=int)
    predictions = (
        Prediction.query.filter_by(user_id=current_user.id)
        .order_by(Prediction.created_at.desc())
        .paginate(page=page, per_page=10, error_out=False)
    )
    return render_template("history.html", predictions=predictions)


@core_bp.route("/history/clear", methods=["POST"])
@login_required
def clear_history():
    Prediction.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash("History cleared successfully.", "success")
    return redirect(url_for("core.history"))


@core_bp.route("/report/<int:id>.pdf")
@login_required
def download_report(id: int):
    prediction = get_owned_prediction_or_404(id)
    chats = (
        ChatMessage.query.filter_by(prediction_id=prediction.id, user_id=current_user.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    pdf_bytes = build_pdf(prediction, chats)
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"fertilizer-report-{id}.pdf",
    )


@core_bp.route("/health")
def health():
    db_status = "ok"
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        db_status = "error"

    model_loaded = ml_service.model_loaded
    rag_loaded = rag_service.loaded
    llm_conf = llm_client.configured

    if not model_loaded or db_status != "ok":
        overall_status = "error"
        status_code = 503
    elif not llm_conf:
        overall_status = "degraded"
        status_code = 200
    else:
        overall_status = "ok"
        status_code = 200

    return jsonify({
        "status": overall_status,
        "model_loaded": model_loaded,
        "model_version": ml_service.meta.get("model_version", "none"),
        "rag_index_loaded": rag_loaded,
        "rag_chunks": len(rag_service.chunks),
        "llm_configured": llm_conf,
        "db": db_status,
    }), status_code

