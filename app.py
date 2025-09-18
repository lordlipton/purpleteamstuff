import string
import random
import time
import threading
import json
from flask import Flask, request, jsonify, render_template_string

# --- Configuration ---
FLAG_LIFETIME_SECONDS = 300  # 5 minutes
BLUE_TEAM_SCORE_INTERVAL_SECONDS = 300 # 5 minutes
TEAM_API_KEY = "SECRET_API_KEY_HERE" # IMPORTANT: Change this to a secure, random key

# --- Global State ---
# This dictionary will hold our application's state. Using a dictionary
# makes it mutable, which is easier to manage across threads.
app_state = {
    "current_flag": "flag{this_is_the_initial_flag}",
    "red_team_score": 0,
    "blue_team_score": 0,
    "flag_submitted_this_round": False
}

# --- Flag and Score Logic ---
def generate_new_flag(length=32):
    """Generates a new, random CTF-style flag."""
    alphabet = string.ascii_letters + string.digits
    random_part = ''.join(random.choice(alphabet) for _ in range(length))
    return f"flag{{{random_part}}}"

def flag_rotation_thread():
    """A background thread that generates a new flag at a set interval."""
    print("Flag rotation thread started.")
    while True:
        print(f"[{time.ctime()}] Generating new flag...")
        new_flag = generate_new_flag()
        app_state['current_flag'] = new_flag
        app_state['flag_submitted_this_round'] = False # Reset submission status
        print(f"[{time.ctime()}] New flag is: {app_state['current_flag']}")
        time.sleep(FLAG_LIFETIME_SECONDS)

def blue_team_score_thread():
    """A background thread that awards points to the Blue team periodically."""
    print("Blue team scoring thread started.")
    while True:
        time.sleep(BLUE_TEAM_SCORE_INTERVAL_SECONDS)
        # Award points only if the flag wasn't captured in the last interval
        if not app_state['flag_submitted_this_round']:
            app_state['blue_team_score'] += 5
            print(f"[{time.ctime()}] Blue team scored! New score: {app_state['blue_team_score']}")

# --- Flask Web Application ---
app = Flask(__name__)

# A simple HTML template for the front page where users can submit the flag
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CTF Scoreboard</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: #f0f2f5; }
        .container { background-color: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); text-align: center; max-width: 450px; width: 90%; }
        h1 { color: #333; }
        .scoreboard { display: flex; justify-content: space-around; margin: 20px 0; padding: 10px; background-color: #f8f9fa; border-radius: 8px; }
        .team-score { font-size: 24px; font-weight: bold; }
        .red { color: #dc3545; }
        .blue { color: #007bff; }
        p { color: #666; }
        input[type="text"] { width: calc(100% - 22px); padding: 10px; margin-top: 20px; border: 1px solid #ccc; border-radius: 6px; }
        input[type="submit"] { width: 100%; padding: 12px; margin-top: 10px; border: none; border-radius: 6px; background-color: #007bff; color: white; font-size: 16px; cursor: pointer; transition: background-color 0.3s; }
        input[type="submit"]:hover { background-color: #0056b3; }
        .message { margin-top: 20px; font-weight: bold; }
        .correct { color: #28a745; }
        .incorrect { color: #dc3545; }
        .info { color: #ffc107; }
    </style>
</head>
<body>
    <div class="container">
        <h1>CTF Scoreboard</h1>
        <div class="scoreboard">
            <div>
                <span class="team-score red">Red Team</span>
                <p class="team-score red">{{ red_score }}</p>
            </div>
            <div>
                <span class="team-score blue">Blue Team</span>
                <p class="team-score blue">{{ blue_score }}</p>
            </div>
        </div>
        <h2>Submit Flag</h2>
        <p>Enter the flag you found on the target machine.</p>
        <form method="POST" action="/api/submit_flag">
            <input type="text" name="flag" placeholder="flag{...}" required>
            <input type="submit" value="Submit">
        </form>
        {% if message %}
            <p class="message {{ 'correct' in message if message else '' }} {{ 'Incorrect' in message if message else 'incorrect' }} {{ 'already' in message if message else 'info' }}">{{ message }}</p>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    """Serves the main page for manual flag submission."""
    return render_template_string(
        HTML_TEMPLATE,
        red_score=app_state['red_team_score'],
        blue_score=app_state['blue_team_score']
    )

# --- API Endpoints ---

@app.route("/api/get_current_flag", methods=["GET"])
def get_current_flag():
    """API endpoint for client scripts to fetch the current flag."""
    # Security Check: Ensure the request has the correct API key
    auth_header = request.headers.get('Authorization')
    if not auth_header or auth_header != f"Bearer {TEAM_API_KEY}":
        return jsonify({"error": "Unauthorized"}), 401

    return jsonify({"flag": app_state['current_flag']})

@app.route("/api/submit_flag", methods=["POST"])
def submit_flag():
    """
    API endpoint for players/clients to submit a flag and check if it's correct.
    This can be used from the web UI or by the client script as a health check.
    """
    submitted_flag = ""
    # Handle both JSON and form submissions
    if request.is_json:
        data = request.get_json()
        submitted_flag = data.get("flag")
    else:
        submitted_flag = request.form.get("flag")

    if not submitted_flag:
        return jsonify({"error": "No flag provided"}), 400

    message = ""
    status_code = 200

    if submitted_flag == app_state['current_flag']:
        if not app_state['flag_submitted_this_round']:
            app_state['red_team_score'] += 10 # Or any points you want
            app_state['flag_submitted_this_round'] = True
            message = "Correct! Flag accepted. Red Team scores!"
        else:
            message = "Correct, but this flag has already been submitted."
            status_code = 400 # Bad request as it's a duplicate
    else:
        message = "Incorrect flag. Try again."
        status_code = 400

    # For the web UI
    if request.form:
        return render_template_string(
            HTML_TEMPLATE,
            message=message,
            red_score=app_state['red_team_score'],
            blue_score=app_state['blue_team_score']
        ), 200 # Return 200 to render the page, even if flag is wrong
    
    # For API clients
    if "Incorrect" in message or "already" in message:
        return jsonify({"status": "failure", "message": message}), status_code
    else:
        return jsonify({"status": "success", "message": message})


if __name__ == "__main__":
    # Start the flag rotation in a separate thread
    rotation_daemon = threading.Thread(target=flag_rotation_thread, daemon=True)
    rotation_daemon.start()

    # Start the blue team scoring in a separate thread
    blue_team_daemon = threading.Thread(target=blue_team_score_thread, daemon=True)
    blue_team_daemon.start()
    
    # Run the Flask web server
    # Use host='0.0.0.0' to make it accessible from other machines on the network
    app.run(host='0.0.0.0', port=5000)
