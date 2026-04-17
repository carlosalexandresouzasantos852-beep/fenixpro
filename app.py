from flask import Flask, render_template, request, jsonify, redirect, session
import requests
import os
import json

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fenixx_secret")

# =========================
# CONFIG DISCORD
# =========================

CLIENT_ID = "1494377772661870622"
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = "https://fenixpro-production.up.railway.app/callback"

if not CLIENT_SECRET:
    raise RuntimeError("DISCORD_CLIENT_SECRET não encontrado nas variáveis do Railway")

API_BASE = "https://discord.com/api"

# =========================
# ROTAS WEB
# =========================

@app.route("/")
def home():
    if "user" in session:
        return redirect("/painel")
    return redirect("/login")


@app.route("/painel")
def painel():
    if "user" not in session:
        return redirect("/login")
    return render_template("painel.html", user=session["user"])


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")
    return render_template("dashboard.html", user=session["user"])


# =========================
# LOGIN DISCORD
# =========================

@app.route("/login")
def login():
    return redirect(
        f"{API_BASE}/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20guilds"
    )


@app.route("/callback")
def callback():
    code = request.args.get("code")

    if not code:
        return "❌ Código de autorização não recebido.", 400

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    token_response = requests.post(
        f"{API_BASE}/oauth2/token",
        data=data,
        headers=headers
    )
    token = token_response.json()

    access_token = token.get("access_token")

    if not access_token:
        return f"❌ Erro ao obter token: {token}", 400

    user = requests.get(
        f"{API_BASE}/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
    ).json()

    guilds = requests.get(
        f"{API_BASE}/users/@me/guilds",
        headers={"Authorization": f"Bearer {access_token}"},
    ).json()

    session["user"] = user
    session["guilds"] = guilds
    session["token"] = access_token

    return redirect("/painel")


# =========================
# API
# =========================

@app.route("/api/user")
def api_user():
    return jsonify(session.get("user", {}))


@app.route("/api/guilds")
def api_guilds():
    return jsonify(session.get("guilds", []))


@app.route("/api/config", methods=["POST"])
def salvar_config():
    data = request.json

    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    return jsonify({"status": "ok"})


# =========================
# LOGOUT
# =========================

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# =========================
# RUN
# =========================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)