import string
import random
import time
import threading
import json
from flask import Flask, request, jsonify, render_template_string

# --- Configuration ---
FLAG_LIFETIME_SECONDS = 300  # 5 minutes
TEAM_API_KEY = "SECRET_API_KEY_HERE" # IMPORTANT: Change this to a secure, random key

# --- Global State ---
# This dictionary will hold our application's state. Using a dictionary
# makes it mutable, which is easier to manage across threads.
app_state = {
    "current_user_flag": "flag{this_is_the_initial_user_flag}",
    "current_root_flag": "flag{this_is_the_initial_root_flag}",
    "red_team_score": 0,
    "blue_team_score": 15, # Blue team starts with 15 points
    "user_flag_submitted_this_round": False,
    "root_flag_submitted_this_round": False
}

# --- Flag and Score Logic ---
def generate_new_flag(prefix, length=28):
    """Generates a new, random CTF-style flag with a prefix (user or root)."""
    alphabet = string.ascii_letters + string.digits
    random_part = ''.join(random.choice(alphabet) for _ in range(length))
    return f"flag{{{prefix}_{random_part}}}"

def flag_rotation_thread():
    """A background thread that generates new user and root flags at a set interval."""
    print("Flag rotation thread started.")
    while True:
        print(f"[{time.ctime()}] New round starting. Resetting scores and generating new flags...")
        
        # Reset scores for the new round
        app_state['red_team_score'] = 0
        app_state['blue_team_score'] = 15
        
        new_user_flag = generate_new_flag("user")
        new_root_flag = generate_new_flag("root")
        
        app_state['current_user_flag'] = new_user_flag
        app_state['current_root_flag'] = new_root_flag
        app_state['user_flag_submitted_this_round'] = False
        app_state['root_flag_submitted_this_round'] = False
        
        print(f"[{time.ctime()}] Scores have been reset. Red: 0, Blue: 15")
        print(f"[{time.ctime()}] New User Flag is: {app_state['current_user_flag']}")
        print(f"[{time.ctime()}] New Root Flag is: {app_state['current_root_flag']}")
        time.sleep(FLAG_LIFETIME_SECONDS)

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
        <p>Enter the user or root flag you found on the target machine.</p>
        <form method="POST" action="/api/submit_flag">
            <input type="text" name="flag" placeholder="flag{...}" required>
            <input type="submit" value="Submit">
        </form>
        {% if message %}
            <p class="message {{ 'Correct!' in message if message else '' }} {{ 'Incorrect' in message if message else 'incorrect' }} {{ 'already' in message if message else 'info' }}">{{ message }}</p>
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
    """API endpoint for client scripts to fetch the current flags."""
    # Security Check: Ensure the request has the correct API key
    auth_header = request.headers.get('Authorization')
    if not auth_header or auth_header != f"Bearer {TEAM_API_KEY}":
        return jsonify({"error": "Unauthorized"}), 401

    return jsonify({
        "user_flag": app_state['current_user_flag'],
        "root_flag": app_state['current_root_flag']
    })

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
    status_code = 400 # Default to failure/incorrect

    # Check against user flag
    if submitted_flag == app_state['current_user_flag']:
        if not app_state['user_flag_submitted_this_round']:
            app_state['red_team_score'] += 5
            app_state['blue_team_score'] -= 5
            app_state['user_flag_submitted_this_round'] = True
            message = "Correct! User flag accepted. Red Team scores 5 points!"
            status_code = 200
        else:
            message = "Correct, but the user flag has already been submitted this round."
    # Check against root flag
    elif submitted_flag == app_state['current_root_flag']:
        if not app_state['root_flag_submitted_this_round']:
            app_state['red_team_score'] += 10
            app_state['blue_team_score'] -= 10
            app_state['root_flag_submitted_this_round'] = True
            message = "Correct! Root flag accepted. Red Team scores 10 points!"
            status_code = 200
        else:
            message = "Correct, but the root flag has already been submitted this round."
    # Incorrect flag
    else:
        message = "Incorrect flag. Try again."

    # For the web UI
    if request.form:
        return render_template_string(
            HTML_TEMPLATE,
            message=message,
            red_score=app_state['red_team_score'],
            blue_score=app_state['blue_team_score']
        ), 200 # Return 200 to render the page, even if flag is wrong
    
    # For API clients
    if status_code != 200:
        return jsonify({"status": "failure", "message": message}), status_code
    else:
        return jsonify({"status": "success", "message": message})


if __name__ == "__main__":
    # Start the flag rotation in a separate thread
    rotation_daemon = threading.Thread(target=flag_rotation_thread, daemon=True)
    rotation_daemon.start()
    
    # Run the Flask web server
    # Use host='0.0.0.0' to make it accessible from other machines on the network
    app.run(host='0.0.0.0', port=5000)
