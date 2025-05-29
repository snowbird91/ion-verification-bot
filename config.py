import os
import json
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ION_CLIENT_ID = os.getenv("ION_CLIENT_ID")
ION_CLIENT_SECRET = os.getenv("ION_CLIENT_SECRET")
ION_REDIRECT_URI = os.getenv("ION_REDIRECT_URI")
FLASK_BASE_URL = os.getenv("FLASK_BASE_URL")

GUILD_ID = int(os.getenv("GUILD_ID"))
VERIFY_CHANNEL_ID = int(os.getenv("VERIFY_CHANNEL_ID"))

ROLE_TO_REMOVE_NAME = os.getenv("ROLE_TO_REMOVE_NAME")
CLASS_YEAR_ROLES = json.loads(os.getenv("CLASS_YEAR_ROLES_JSON", "{}"))

# For local development without HTTPS for the callback (ION requires HTTPS by default for callbacks)
# SET THIS TO '0' or remove if your callback IS served over HTTPS
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'