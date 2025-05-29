from flask import Flask, redirect, request, session, render_template_string
from requests_oauthlib import OAuth2Session
from oauthlib.oauth2.rfc6749.errors import TokenExpiredError
import config
import discord
import os
from discord.utils import get
import asyncio
import logging
import uuid # For generating state

app = Flask(__name__)
app.secret_key = os.urandom(24) # For session management (to store state temporarily)
logging.basicConfig(level=logging.INFO)

# --- HTML Templates ---
SUCCESS_TEMPLATE = """
<!DOCTYPE html><html><head><title>Verification Success</title></head>
<body><h1>Verification Successful!</h1><p>{{ message }}</p>
<p>You can now close this tab.</p></body></html>
"""
ERROR_TEMPLATE = """
<!DOCTYPE html><html><head><title>Verification Error</title></head>
<body><h1>Verification Error</h1><p>{{ message }}</p>
<p>Please try again or contact an admin.</p></body></html>
"""

# This dictionary will temporarily store the Discord user ID mapped to the OAuth state
# In a production app, you might use a database for this
pending_verifications = {}

async def assign_discord_roles(discord_user_id: int, guild_id: int, ion_username: str):
    """
    Assigns roles to a Discord user based on their ION username.
    This function runs within the Flask app's context but uses discord.py.
    """
    intents = discord.Intents.default()
    intents.members = True # Crucial for fetching members
    intents.guilds = True  # For guild operations

    # Create a new client instance for this task.
    # In a more complex setup, you might have a shared client or IPC.
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        logging.info(f"Role assigner client logged in as {client.user}")
        guild = client.get_guild(guild_id)
        if not guild:
            logging.error(f"Could not find guild with ID {guild_id}")
            await client.close()
            return

        member = guild.get_member(discord_user_id)
        if not member:
            logging.error(f"Could not find member with ID {discord_user_id} in guild {guild.name}")
            await client.close()
            return

        logging.info(f"Processing roles for {member.name} ({member.id}) based on ION username: {ion_username}")

        # 1. Determine class year role
        class_year_str = ion_username[:4] # e.g., "2025" from "2025jdoe"
        assigned_role_name = None
        if class_year_str.isdigit() and class_year_str in config.CLASS_YEAR_ROLES:
            assigned_role_name = config.CLASS_YEAR_ROLES[class_year_str]
        elif "Alumni" in config.CLASS_YEAR_ROLES and not class_year_str.isdigit(): # Basic check, improve if needed
             # This is a simplistic check. You might need better logic for alumni/faculty.
             # For example, checking if the username contains only letters after initial digits,
             # or if it doesn't start with 4 digits.
             is_student_format = len(ion_username) > 4 and ion_username[:4].isdigit()
             if not is_student_format: # Crude assumption for non-student formats
                 if "Faculty" in config.CLASS_YEAR_ROLES and any(c.isalpha() for c in ion_username if not c.isdigit()): # if it has letters and not typical student
                      assigned_role_name = config.CLASS_YEAR_ROLES.get("Faculty") # Check faculty first
                 if not assigned_role_name and "Alumni" in config.CLASS_YEAR_ROLES:
                      assigned_role_name = config.CLASS_YEAR_ROLES.get("Alumni")

        if not assigned_role_name: # Default or fallback if no specific year/type matched
            if "Default" in config.CLASS_YEAR_ROLES: # Example: a "Verified" role
                assigned_role_name = config.CLASS_YEAR_ROLES["Default"]
            else:
                 logging.warning(f"No role mapping found for ION user {ion_username} (year: {class_year_str}). Not assigning class year role.")
                 # Even if no year role, we might still want to remove the "Unverified" role
        
        roles_to_add = []
        if assigned_role_name:
            role_to_add = get(guild.roles, name=assigned_role_name)
            if role_to_add:
                roles_to_add.append(role_to_add)
                logging.info(f"Will add role: {role_to_add.name}")
            else:
                logging.warning(f"Role '{assigned_role_name}' not found in server.")

        # 2. Role to remove
        role_to_remove_obj = None
        if config.ROLE_TO_REMOVE_NAME:
            role_to_remove_obj = get(guild.roles, name=config.ROLE_TO_REMOVE_NAME)
            if role_to_remove_obj:
                logging.info(f"Will remove role: {role_to_remove_obj.name}")
            else:
                logging.warning(f"Role to remove '{config.ROLE_TO_REMOVE_NAME}' not found in server.")
        
        try:
            if roles_to_add:
                await member.add_roles(*roles_to_add, reason=f"Verified via ION as {ion_username}")
                logging.info(f"Added role(s) {[r.name for r in roles_to_add]} to {member.name}")
            if role_to_remove_obj and role_to_remove_obj in member.roles:
                await member.remove_roles(role_to_remove_obj, reason="Verified via ION")
                logging.info(f"Removed role {role_to_remove_obj.name} from {member.name}")
            logging.info(f"Role assignment for {member.name} complete.")
        except discord.Forbidden:
            logging.error(f"Bot lacks permissions to manage roles for {member.name} or modify roles.")
        except Exception as e:
            logging.error(f"Error managing roles for {member.name}: {e}")
        finally:
            await client.close() # Important to close the client

    try:
        await client.login(config.DISCORD_BOT_TOKEN)
        await client.connect(reconnect=False) # Connect and run on_ready, then will disconnect due to finally
    except Exception as e:
        logging.error(f"Failed to run discord client for role assignment: {e}")


@app.route('/')
def index():
    return "Discord ION Verifier Bot Web Interface. Waiting for verification requests."

@app.route('/start-verify')
def start_verify():
    discord_user_id = request.args.get('user_id')
    guild_id = request.args.get('guild_id')

    if not discord_user_id or not guild_id:
        return render_template_string(ERROR_TEMPLATE, message="Missing user_id or guild_id."), 400

    # Generate a unique state value
    oauth_state = str(uuid.uuid4())
    
    # Store the discord_user_id and guild_id with this state
    # In a real app, this might be a short-lived entry in a database
    pending_verifications[oauth_state] = {
        "discord_user_id": int(discord_user_id),
        "guild_id": int(guild_id)
    }
    logging.info(f"Starting verification for Discord User ID: {discord_user_id}, Guild ID: {guild_id}, State: {oauth_state}")


    oauth = OAuth2Session(config.ION_CLIENT_ID,
                          redirect_uri=config.ION_REDIRECT_URI,
                          scope=["read"]) # We only need to read profile info
    
    authorization_url, state = oauth.authorization_url(
        "https://ion.tjhsst.edu/oauth/authorize/",
        state=oauth_state # Pass our generated state to ION
    )
    
    logging.info(f"Redirecting user to ION: {authorization_url}")
    return redirect(authorization_url)


@app.route('/callback')
def callback():
    authorization_code = request.args.get('code')
    returned_state = request.args.get('state')

    logging.info(f"Received callback from ION. Code: {'present' if authorization_code else 'absent'}, State: {returned_state}")

    if not returned_state or returned_state not in pending_verifications:
        logging.error("Invalid or missing state parameter in callback.")
        return render_template_string(ERROR_TEMPLATE, message="Invalid state. Verification session might have expired or been tampered with."), 400
    
    verification_data = pending_verifications.pop(returned_state) # Retrieve and remove
    discord_user_id = verification_data["discord_user_id"]
    guild_id = verification_data["guild_id"]

    if not authorization_code:
        logging.error("No authorization code provided by ION.")
        return render_template_string(ERROR_TEMPLATE, message="ION authorization failed or was denied."), 400

    oauth = OAuth2Session(config.ION_CLIENT_ID, redirect_uri=config.ION_REDIRECT_URI)
    
    try:
        logging.info("Fetching token from ION...")
        token = oauth.fetch_token("https://ion.tjhsst.edu/oauth/token/",
                                  code=authorization_code,
                                  client_secret=config.ION_CLIENT_SECRET)
        logging.info("Token fetched successfully.")
    except Exception as e:
        logging.error(f"Error fetching token: {e}")
        return render_template_string(ERROR_TEMPLATE, message=f"Could not fetch token from ION: {e}"), 500

    try:
        logging.info("Fetching profile from ION...")
        profile_response = oauth.get("https://ion.tjhsst.edu/api/profile")
        profile_response.raise_for_status() # Raise an exception for bad status codes
        profile_data = profile_response.json()
        ion_username = profile_data.get('ion_username')
        logging.info(f"Profile fetched successfully. ION Username: {ion_username}")

        if not ion_username:
            logging.error("ion_username not found in profile data.")
            return render_template_string(ERROR_TEMPLATE, message="Could not retrieve ION username from profile."), 500
        
        # Run the Discord role assignment logic
        # This runs the discord.py client login, task, and logout
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
             loop.run_until_complete(assign_discord_roles(discord_user_id, guild_id, ion_username))
        finally:
             loop.close()

        return render_template_string(SUCCESS_TEMPLATE, message=f"You have been verified as {ion_username}. Roles are being updated.")

    except TokenExpiredError:
        # This example doesn't implement token refresh for simplicity,
        # as the token is used immediately.
        logging.error("Token expired (should not happen in this flow).")
        return render_template_string(ERROR_TEMPLATE, message="Access token expired unexpectedly."), 500
    except Exception as e:
        logging.error(f"Error fetching profile or assigning roles: {e}")
        return render_template_string(ERROR_TEMPLATE, message=f"An error occurred: {e}"), 500

if __name__ == '__main__':
    # For production, use a proper WSGI server like Gunicorn or Waitress
    # Make sure ION_REDIRECT_URI matches how this server is accessed
    # If ION_REDIRECT_URI is http://localhost:5000/callback, run on 0.0.0.0 for external access if needed
    # or use ngrok to expose localhost:5000
    app.run(host='0.0.0.0', port=5000, debug=True) # debug=False for production