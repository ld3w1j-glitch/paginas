from flask import Flask, jsonify

from portal_core.security import csrf_protect_request, get_csrf_token


def create_security_app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", TESTING=True, TEST_CSRF=True, CSRF_ENABLED=True)

    @app.before_request
    def protect():
        csrf_protect_request()

    @app.get("/token")
    def token():
        return jsonify({"token": get_csrf_token()})

    @app.post("/change")
    def change():
        return jsonify({"ok": True})

    return app


def test_csrf_rejects_missing_token_and_accepts_valid_token():
    app = create_security_app()
    with app.test_client() as client:
        token = client.get("/token").get_json()["token"]
        assert client.post("/change").status_code == 400
        response = client.post("/change", headers={"X-CSRF-Token": token})
        assert response.status_code == 200
        assert response.get_json()["ok"] is True
