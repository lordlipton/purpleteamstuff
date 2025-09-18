import os
import time
import json
import requests # Make sure to install this: pip install requests

# --- Configuration ---
# This is the address of your central Flask web app.
# IMPORTANT: Change this to the actual IP address or hostname of your server.
FLAG_AUTHORITY_URL = "http://192.168.1.100:5000/api/get_current_flag"

# The local file paths for this specific machine.
# Ensure the user running the script has permissions for this path.
USER_FLAG_PATH = "/home/ctf_user/flag.txt" 
# Writing to /root requires running the script with sudo.
ROOT_FLAG_PATH = "/root/flag.txt"

# The secret API key must match the one set on the server.
TEAM_API_KEY = "SECRET_API_KEY_HERE" # IMPORTANT: Change this to match the server's key

# Interval in seconds to fetch and update the flag
UPDATE_INTERVAL_SECONDS = 300  # 5 minutes

def fetch_current_flag():
    """Fetches the current flag from the central server."""
    print(f"\n[{time.ctime()}] Fetching flag from {FLAG_AUTHORITY_URL}")
    try:
        headers = {'Authorization': f'Bearer {TEAM_API_KEY}'}
        response = requests.get(FLAG_AUTHORITY_URL, headers=headers, timeout=10)
        
        if response.status_code == 200:
            flag = response.json().get('flag')
            print(f"[{time.ctime()}] Successfully fetched flag: {flag}")
            return flag
        else:
            print(f"[{time.ctime()}] [ERROR] Failed to fetch flag. Status: {response.status_code}, Response: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"[{time.ctime()}] [ERROR] Network error while fetching flag: {e}")
        return None

def update_local_flags(new_flag):
    """Writes the new flag to the local user and root flag files."""
    print(f"[{time.ctime()}] Attempting to write new flag to local files...")

    # --- Write User Flag ---
    try:
        # Ensure the directory exists
        user_dir = os.path.dirname(USER_FLAG_PATH)
        if not os.path.exists(user_dir):
            os.makedirs(user_dir)
        with open(USER_FLAG_PATH, 'w') as f:
            f.write(new_flag)
        print(f"[{time.ctime()}] [SUCCESS] Wrote flag to {USER_FLAG_PATH}")
    except IOError as e:
        print(f"[{time.ctime()}] [ERROR] Could not write to user flag file {USER_FLAG_PATH}: {e}")
        print("    Check file permissions and if the path is correct.")

    # --- Write Root Flag ---
    # This part requires the script to be run with root privileges (sudo)
    if os.geteuid() == 0:
        try:
            root_dir = os.path.dirname(ROOT_FLAG_PATH)
            if not os.path.exists(root_dir):
                os.makedirs(root_dir)
            with open(ROOT_FLAG_PATH, 'w') as f:
                f.write(new_flag)
            print(f"[{time.ctime()}] [SUCCESS] Wrote flag to {ROOT_FLAG_PATH}")
        except IOError as e:
            print(f"[{time.ctime()}] [ERROR] Could not write to root flag file {ROOT_FLAG_PATH}: {e}")
    else:
        print(f"[{time.ctime()}] [WARNING] Not running as root. Skipping root flag update at {ROOT_FLAG_PATH}.")


if __name__ == "__main__":
    print("--- CTF Flag Rotator Client ---")
    print(f"Fetching flag every {UPDATE_INTERVAL_SECONDS} seconds.")
    print("Press Ctrl+C to stop.")

    if os.geteuid() != 0:
        print("\n[WARNING] Script is not running as root. It will not be able to update the root flag file.\n")

    try:
        while True:
            current_flag = fetch_current_flag()
            if current_flag:
                update_local_flags(current_flag)
            else:
                print(f"[{time.ctime()}] Skipping local update due to fetch failure.")
            
            print(f"\n[{time.ctime()}] Sleeping for {UPDATE_INTERVAL_SECONDS} seconds...")
            time.sleep(UPDATE_INTERVAL_SECONDS)
            
    except KeyboardInterrupt:
        print("\n\nScript stopped by user. Exiting.")
