from flask import Flask, request, jsonify, render_template
import importlib.util
import pathlib
import json

# load wildfire-desk.py
module_path = pathlib.Path(__file__).parent / "wildfire-desk.py"
spec = importlib.util.spec_from_file_location("wildfire_desk", module_path)
wildfire_desk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wildfire_desk)

app = Flask(__name__)


@app.route("/")
def home():
    community_map = wildfire_desk.get_state_to_communities_map()
    return render_template(
        "index.html",
        state_community_map=community_map,
        state_community_map_json=json.dumps(community_map)
    )


@app.route("/intro", methods=["GET"])
def intro():
    intro_text = wildfire_desk.get_intro()
    return jsonify({"intro": intro_text})


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()

    user_message = data.get("message", "").strip()
    mode = data.get("mode", "grounded").strip().lower()
    use_local_news = data.get("use_local_news", False)
    selected_state = data.get("selected_state", "").strip()
    selected_community = data.get("selected_community", "").strip()

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    if mode not in {"grounded", "general"}:
        mode = "grounded"

    use_local_news = bool(use_local_news)

    print("APP.PY RECEIVED:")
    print("message:", user_message)
    print("mode:", mode)
    print("use_local_news:", use_local_news)
    print("selected_state:", selected_state)
    print("selected_community:", selected_community)

    result = wildfire_desk.chat_with_sage(
        user_message,
        mode=mode,
        use_local_news=use_local_news,
        selected_state=selected_state,
        selected_community=selected_community
    )

    return jsonify(result)


if __name__ == "__main__":
    if not wildfire_desk.setup_sage():
        raise RuntimeError("Failed to set up Sage")

    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)