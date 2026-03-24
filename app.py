from flask import Flask, request, jsonify, render_template
import importlib.util
import pathlib

# Load wildfire-desk.py
module_path = pathlib.Path(__file__).parent / "wildfire-desk.py"
spec = importlib.util.spec_from_file_location("wildfire_desk", module_path)
wildfire_desk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wildfire_desk)

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/intro", methods=["GET"])
def intro():
    intro_text = wildfire_desk.get_intro()
    return jsonify({"intro": intro_text})


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    result = wildfire_desk.chat_with_sage(user_message)
    return jsonify(result)


if __name__ == "__main__":
    if not wildfire_desk.setup_sage():
        raise RuntimeError("Failed to set up Sage")

    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)