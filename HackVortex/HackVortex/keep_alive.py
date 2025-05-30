import requests
import time
import logging
import os
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("keep_alive.log"),
        logging.StreamHandler()
    ]
)

# Get app URL from environment variable or use default
APP_URL = os.environ.get("RENDER_APP_URL", "https://lawcraft-8f7u.onrender.com")

# Interval between requests (13 minutes in seconds)
INTERVAL = 13 * 60

def ping_server():
    """Send a request to the server to keep it alive."""
    try:
        start_time = time.time()
        response = requests.get(APP_URL, timeout=30)
        elapsed_time = time.time() - start_time
        
        if response.status_code == 200:
            logging.info(f"Ping successful! Response time: {elapsed_time:.2f} seconds")
        else:
            logging.warning(f"Ping returned status code {response.status_code}. Response time: {elapsed_time:.2f} seconds")
            
    except requests.RequestException as e:
        logging.error(f"Error pinging server: {e}")

def main():
    """Main function to run the keep-alive script."""
    logging.info("Starting keep-alive script")
    logging.info(f"Target URL: {APP_URL}")
    logging.info(f"Ping interval: {INTERVAL} seconds (13 minutes)")
    
    while True:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logging.info(f"Sending ping at {current_time}")
        
        ping_server()
        
        logging.info(f"Sleeping for {INTERVAL} seconds until next ping")
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main() 