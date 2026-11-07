import re
import pytest
import requests

def test_live_app():
    session = requests.Session()
    base_url = "http://127.0.0.1:5000"

    # 1. Login page to get CSRF token
    try:
        r_login_page = session.get(f"{base_url}/login")
    except Exception:
        pytest.skip("Live server is not running on http://127.0.0.1:5000")
    assert r_login_page.status_code == 200, f"Login page failed: {r_login_page.status_code}"
    csrf_token = re.search(r'name="csrf_token"[^>]*?value="([^"]+)"', r_login_page.text).group(1)

    # 2. Login as demo user
    login_data = {"email": "demo@example.com", "password": "Demo@1234", "csrf_token": csrf_token}
    r_login = session.post(f"{base_url}/login", data=login_data, allow_redirects=True)
    assert r_login.status_code == 200, f"Login failed: {r_login.status_code}"
    assert "demo@example.com" in r_login.text or "Dashboard" in r_login.text or "Logout" in r_login.text

    # 3. Predictor page
    r_pred_page = session.get(f"{base_url}/predictor")
    assert r_pred_page.status_code == 200
    pred_csrf = re.search(r'name="csrf_token"[^>]*?value="([^"]+)"', r_pred_page.text).group(1)

    # 4. Submit prediction (Wheat, 2 acres, medium soil test: N=40, P=20, K=20)
    form_data = {
        "csrf_token": pred_csrf,
        "temperature": 26,
        "humidity": 52,
        "moisture": 38,
        "soil": "Clayey",
        "crop": "Wheat",
        "nitrogen": 40,
        "phosphorous": 20,
        "potassium": 20,
        "rating_n": "Medium",
        "rating_p": "Medium",
        "rating_k": "Medium",
        "area_value": 2.0,
        "area_unit": "acre",
    }
    r_post_pred = session.post(f"{base_url}/predict", data=form_data, allow_redirects=True)
    assert r_post_pred.status_code == 200, f"Predict failed: {r_post_pred.status_code}"
    pred_id_match = re.search(r'/report/(\d+)\.pdf', r_post_pred.text)
    assert pred_id_match, "Could not find report link in result page"
    pred_id = pred_id_match.group(1)
    print(f"Prediction successful! ID: {pred_id}")

    # 5. Check PDF report
    r_pdf = session.get(f"{base_url}/report/{pred_id}.pdf")
    assert r_pdf.status_code == 200, f"PDF failed: {r_pdf.status_code}"
    assert r_pdf.content.startswith(b"%PDF"), "Not a valid PDF file"
    print(f"PDF report generated successfully! Size: {len(r_pdf.content)} bytes")

    # 6. Check Dashboard
    r_dash = session.get(f"{base_url}/dashboard")
    assert r_dash.status_code == 200
    assert "Wheat" in r_dash.text
    print("Dashboard loaded with predictions!")

    # 7. Test Chat API
    chat_data = {"question": "What is the dosage for wheat?", "prediction_id": int(pred_id)}
    r_chat = session.post(f"{base_url}/api/chat", json=chat_data, headers={"X-CSRFToken": pred_csrf})
    assert r_chat.status_code == 200, f"Chat API failed: {r_chat.status_code}"
    chat_resp = r_chat.json()
    print("Chat API response:", chat_resp.get("answer", "")[:80] + "...")

    print("\nALL END-TO-END CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_live_app()
