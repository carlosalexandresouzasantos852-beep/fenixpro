from flask import Flask, render_template, request, jsonify, redirect, session
import requests
import os
import json

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fenixx_secret")

CLIENT_ID     = "1494377772661870622"
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
BOT_TOKEN     = os.getenv("DISCORD_BOT_TOKEN")        # ← NOVO: token do bot
REDIRECT_URI  = "https://fenixpro-production.up.railway.app/callback"

if not CLIENT_SECRET:
    raise RuntimeError("DISCORD_CLIENT_SECRET não encontrado nas variáveis do Railway")

API_BASE    = "https://discord.com/api"
CONFIG_FILE = "config.json"

# =========================
# UTILS
# =========================

def load_json(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

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
# LOGIN DISCORD (OAuth2)
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

    token_response = requests.post(
        f"{API_BASE}/oauth2/token",
        data={
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type":    "authorization_code",
            "code":          code,
            "redirect_uri":  REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    token = token_response.json()
    access_token = token.get("access_token")

    if not access_token:
        return f"❌ Erro ao obter token: {token}", 400

    user = requests.get(
        f"{API_BASE}/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
    ).json()

    session["user"] = {
        "id":          user.get("id"),
        "username":    user.get("username"),
        "avatar":      user.get("avatar"),
        "global_name": user.get("global_name"),
    }
    session["token"] = access_token

    return redirect("/painel")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# =========================
# API — USUÁRIO
# =========================

@app.route("/api/user")
def api_user():
    return jsonify(session.get("user", {}))


# =========================
# API — GUILDS DO USUÁRIO
# =========================

@app.route("/api/guilds")
def api_guilds():
    access_token = session.get("token")
    if not access_token:
        return jsonify([])

    guilds = requests.get(
        f"{API_BASE}/users/@me/guilds",
        headers={"Authorization": f"Bearer {access_token}"},
    ).json()

    if not isinstance(guilds, list):
        return jsonify([])

    # Filtra só owner / admin (ADMINISTRATOR) / MANAGE_GUILD
    guilds_filtradas = []
    for guild in guilds:
        permissions = int(guild.get("permissions", 0))
        is_owner    = guild.get("owner", False)
        is_admin    = (permissions & 0x8) == 0x8
        can_manage  = (permissions & 0x20) == 0x20

        if is_owner or is_admin or can_manage:
            guilds_filtradas.append({
                "id":   guild["id"],
                "name": guild["name"],
                "icon": guild.get("icon"),
                "owner": is_owner,
            })

    return jsonify(guilds_filtradas)


# =========================
# API — GUILDS ONDE O BOT ESTÁ
# Retorna lista de IDs dos servidores onde o bot foi adicionado.
# O frontend compara com a lista do usuário para mostrar
# "Gerenciar" ou "Adicionar".
# =========================

@app.route("/api/bot/guilds")
def api_bot_guilds():
    if "user" not in session:
        return jsonify([])

    if not BOT_TOKEN:
        # Token não configurado: retorna lista vazia
        # O frontend mostrará "Adicionar" em todos os servidores
        return jsonify([])

    resp = requests.get(
        f"{API_BASE}/users/@me/guilds",
        headers={"Authorization": f"Bot {BOT_TOKEN}"},
    )

    if resp.status_code != 200:
        return jsonify([])

    bot_guilds = resp.json()

    if not isinstance(bot_guilds, list):
        return jsonify([])

    # Retorna só os IDs (o frontend usa Set para lookup rápido)
    return jsonify([g["id"] for g in bot_guilds])


# =========================
# API — CONFIG POR SERVIDOR
# =========================

@app.route("/api/config/<guild_id>", methods=["GET"])
def get_config(guild_id):
    config = load_json(CONFIG_FILE)
    return jsonify(config.get(str(guild_id), {}))


@app.route("/api/config/<guild_id>", methods=["POST"])
def save_config(guild_id):
    data = request.json
    if not data:
        return jsonify({"status": "erro", "msg": "Nenhum dado recebido"}), 400

    config = load_json(CONFIG_FILE)
    config[str(guild_id)] = data
    save_json(CONFIG_FILE, config)

    return jsonify({"status": "ok"})

@app.route("/api/guild/<guild_id>/channels")
def api_guild_channels(guild_id):
    if "user" not in session:
        return jsonify({"error": "Não autenticado"}), 401

    if not BOT_TOKEN:
        return jsonify({"error": "BOT_TOKEN não configurado"}), 500

    resp = requests.get(
        f"{API_BASE}/guilds/{guild_id}/channels",
        headers={
            "Authorization": f"Bot {BOT_TOKEN}"
        }
    )

    if resp.status_code != 200:
        return jsonify({"error": resp.json()}), resp.status_code

    channels = resp.json()

    text_channels = []
    categories = []

    for ch in channels:
        if ch["type"] == 0:  # texto
            text_channels.append({
                "id": ch["id"],
                "name": ch["name"]
            })

        elif ch["type"] == 4:  # categoria
            categories.append({
                "id": ch["id"],
                "name": ch["name"]
            })

    return jsonify({
        "text_channels": text_channels,
        "categories": categories
    })

@app.route("/api/guild/<guild_id>/roles")
def api_guild_roles(guild_id):
    if "user" not in session:
        return jsonify({"error": "Não autenticado"}), 401

    if not BOT_TOKEN:
        return jsonify({"error": "BOT_TOKEN não configurado"}), 500

    resp = requests.get(
        f"{API_BASE}/guilds/{guild_id}/roles",
        headers={
            "Authorization": f"Bot {BOT_TOKEN}"
        }
    )

    if resp.status_code != 200:
        return jsonify({"error": resp.json()}), resp.status_code

    roles = resp.json()

    roles_formatados = [
        {"id": r["id"], "name": r["name"]}
        for r in roles
        if r["name"] != "@everyone"
    ]

    return jsonify(roles_formatados)

@app.route("/api/guild/<guild_id>/channels")
def api_guild_channels(guild_id):
    if "user" not in session:
        return jsonify({"error": "Não autenticado"}), 401

    if not BOT_TOKEN:
        return jsonify({"error": "DISCORD_BOT_TOKEN não configurado"}), 500

    resp = requests.get(
        f"{API_BASE}/guilds/{guild_id}/channels",
        headers={"Authorization": f"Bot {BOT_TOKEN}"}
    )

    if resp.status_code != 200:
        return jsonify({"error": resp.text}), resp.status_code

    channels = resp.json()

    text_channels = []
    categories = []

    for ch in channels:
        if ch["type"] == 0:  # canal de texto
            text_channels.append({
                "id": ch["id"],
                "name": ch["name"]
            })
        elif ch["type"] == 4:  # categoria
            categories.append({
                "id": ch["id"],
                "name": ch["name"]
            })

    return jsonify({
        "text_channels": text_channels,
        "categories": categories
    })


@app.route("/api/guild/<guild_id>/roles")
def api_guild_roles(guild_id):
    if "user" not in session:
        return jsonify({"error": "Não autenticado"}), 401

    if not BOT_TOKEN:
        return jsonify({"error": "DISCORD_BOT_TOKEN não configurado"}), 500

    resp = requests.get(
        f"{API_BASE}/guilds/{guild_id}/roles",
        headers={"Authorization": f"Bot {BOT_TOKEN}"}
    )

    if resp.status_code != 200:
        return jsonify({"error": resp.text}), resp.status_code

    roles = resp.json()

    roles_formatados = [
        {"id": r["id"], "name": r["name"]}
        for r in roles
        if r["name"] != "@everyone"
    ]

    return jsonify(roles_formatados)

# =========================
# RUN
# =========================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)