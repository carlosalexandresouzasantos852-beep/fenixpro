from flask import Flask, render_template, request, jsonify
import json
import os

app = Flask(__name__)

CONFIG_FILE = "../bot/config.json"  # 🔥 importante (aponta pro bot)

# =========================
# ROTAS WEB
# =========================

@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/painel")
def painel():
    return render_template("painel.html")


# =========================
# API (ligação com bot)
# =========================

@app.route("/api/config", methods=["POST"])
def salvar_config():
    try:
        data = request.json

        if not os.path.exists(CONFIG_FILE):
            config = {}
        else:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)

        guild_id = str(data.get("guild_id"))

        config[guild_id] = data

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

        return jsonify({"status": "ok"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================
# WEBHOOK MERCADO PAGO
# =========================

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json

        print("🔥 Webhook recebido:", data)

        # Aqui depois você pode integrar com seu bot
        # (ativar plano automático)

        return "ok", 200

    except Exception as e:
        print("Erro webhook:", e)
        return "erro", 500


# =========================
# RUN (Railway obrigatório)
# =========================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)