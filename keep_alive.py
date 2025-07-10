# keep_alive.py

from flask import Flask
from threading import Thread

app = Flask(__name__)


@app.route('/')
def home():
    return "Bot is alive!"


def run_flask_server():
    # Replit sometimes uses port 5000, sometimes 8080.
    # 0.0.0.0 means it listens on all available interfaces.
    app.run(host='0.0.0.0', port=8080)


def start_keep_alive_server():
    """
    Starts the Flask web server in a separate thread.
    This function should be called from your main bot file.
    """
    server_thread = Thread(target=run_flask_server)
    server_thread.start()
    print("Flask server started in a separate thread.")


# You can test this file directly if you want, but for the bot,
# we'll import start_keep_alive_server into main.py
# if __name__ == '__main__':
#     start_keep_alive_server()