# webserver.py
from flask import Flask
from threading import Thread
import os # Import the os module to access environment variables

app = Flask('')

@app.route('/')
def home():
    """
    A simple home route for the web server.
    This route is often used by hosting platforms like Render for health checks.
    """
    return "Bot is alive!"

def run():
    """
    Starts the Flask web server.
    It binds to 0.0.0.0 and gets the port from the 'PORT' environment variable,
    defaulting to 8080 if the variable is not set.
    """
    # Use host='0.0.0.0' to make the server accessible from outside the container
    # Use port=os.environ.get('PORT', 8080) if your hosting platform provides a PORT env variable
    # For Render, typically port 10000 is used for web services, but 8080 is a common default.
    # Render will automatically set the PORT environment variable.
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))) # Cast port to int

def keep_alive():
    """
    Starts the web server in a separate thread.
    This allows the main bot process to continue running without being blocked by the web server.
    """
    server_thread = Thread(target=run)
    server_thread.start()
    print("Web server started in a separate thread.")

if __name__ == '__main__':
    # This block will only run if webserver.py is executed directly.
    # In a Render setup, bot.py will import and call keep_alive().
    # For local testing of the web server:
    print("Running web server directly for testing...")
    keep_alive()
    print(f"Access http://127.0.0.1:{os.environ.get('PORT', 8080)} in your browser to test.")
    # For bot integration, the bot's event loop keeps the process alive.
