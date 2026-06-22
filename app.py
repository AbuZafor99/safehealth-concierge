from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from workflow.graph import SafeHealthWorkflow
import os

load_dotenv()

# Map GEMINI_API_KEY → GOOGLE_API_KEY which is what the google-genai SDK reads
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")

app = Flask(__name__, static_folder='ui', static_url_path='')
CORS(app)

workflow = SafeHealthWorkflow()


@app.route('/')
def index():
    return send_from_directory('ui', 'index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_input = data.get('message')
    sender_id = data.get('sender_id', 'member_01')

    if not user_input:
        return jsonify({"error": "No message provided"}), 400

    response, security_status = workflow.run(user_input, sender_id)
    return jsonify({
        "response": response,
        "security_status": security_status,
        "trace": workflow.last_trace,
    })


@app.route('/api/profile/<member_id>', methods=['GET'])
def get_profile(member_id):
    from mcp_server import server
    profile = server.get_family_member_profile(member_id)
    return jsonify(profile)


@app.route('/api/logs/<member_id>', methods=['GET'])
def get_logs(member_id):
    result = workflow.get_logs(member_id)
    return jsonify(result)


@app.route('/api/reset', methods=['POST'])
def reset_daily():
    result = workflow.reset_daily_flags()
    return jsonify(result)


if __name__ == '__main__':
    app.run(port=5001, debug=True)
