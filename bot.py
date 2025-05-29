import discord
from discord.ext import commands
from discord.ui import Button, View
import config
import logging

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.message_content = True # If you use message commands
intents.members = True # Needed for on_ready guild access
intents.guilds = True  # Needed for on_ready guild access

bot = commands.Bot(command_prefix="!", intents=intents) # Prefix doesn't matter much for buttons

class VerificationView(View):
    def __init__(self, base_url: str, guild_id: int):
        super().__init__(timeout=None) # Persistent view
        self.base_url = base_url
        self.guild_id = guild_id

        # The custom_id is important for persistent views
        verify_button = Button(label="Verify with ION", style=discord.ButtonStyle.green, custom_id="verify_ion_button")
        verify_button.callback = self.verify_button_callback
        self.add_item(verify_button)

    async def verify_button_callback(self, interaction: discord.Interaction):
        # Construct the unique URL for this user to start the OAuth flow
        # This URL points to your Flask app's /start-verify endpoint
        verification_start_url = f"{self.base_url}/start-verify?user_id={interaction.user.id}&guild_id={self.guild_id}"
        
        logging.info(f"User {interaction.user.name} ({interaction.user.id}) clicked verify. Sending link: {verification_start_url}")
        
        await interaction.response.send_message(
            f"Please click this link to verify with your TJHSST ION account: {verification_start_url}\n"
            "Make sure you are logged into the correct ION account in your browser.",
            ephemeral=True # Only the user who clicked can see this
        )

@bot.event
async def on_ready():
    logging.info(f'{bot.user.name} has connected to Discord!')
    
    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        logging.error(f"Bot could not find Guild with ID: {config.GUILD_ID}. Ensure it's correct and bot is in the server.")
        return

    channel = guild.get_channel(config.VERIFY_CHANNEL_ID)
    if not channel:
        logging.error(f"Bot could not find Channel with ID: {config.VERIFY_CHANNEL_ID} in guild {guild.name}.")
        return

    # Check if a message with the button already exists to avoid spamming
    # This is a simple check; more robust would involve storing message ID
    message_found = False
    async for msg in channel.history(limit=20): # Check last 20 messages
        if msg.author == bot.user and msg.components:
            for row in msg.components:
                for component in row.children:
                    if isinstance(component, Button) and component.custom_id == "verify_ion_button":
                        logging.info("Verification message with button already exists in the channel.")
                        message_found = True
                        # Optionally, re-register the view if it's persistent and bot restarted
                        bot.add_view(VerificationView(base_url=config.FLASK_BASE_URL, guild_id=config.GUILD_ID))
                        break
                if message_found: break
            if message_found: break
    
    if not message_found:
        logging.info(f"Sending new verification message to channel: {channel.name}")
        view = VerificationView(base_url=config.FLASK_BASE_URL, guild_id=config.GUILD_ID)
        try:
            await channel.send(
                "**TJHSST Student Verification**\n\n"
                "Click the button below to verify your identity using your TJHSST ION account. "
                "This will assign you the appropriate class year role and remove any unverified roles.",
                view=view
            )
            logging.info("Verification message sent.")
        except discord.Forbidden:
            logging.error(f"Bot does not have permission to send messages in channel {channel.name} ({channel.id}).")
        except Exception as e:
            logging.error(f"Failed to send verification message: {e}")
    else:
        # Ensure the view is re-registered if the bot restarts, for persistent views
        # If you used `super().__init__(timeout=None)` for the View.
        bot.add_view(VerificationView(base_url=config.FLASK_BASE_URL, guild_id=config.GUILD_ID))
        logging.info("VerificationView re-registered for persistent button.")


if __name__ == '__main__':
    if not config.DISCORD_BOT_TOKEN:
        logging.error("DISCORD_BOT_TOKEN not found in .env. Exiting.")
    elif not config.ION_CLIENT_ID or not config.ION_CLIENT_SECRET:
        logging.error("ION_CLIENT_ID or ION_CLIENT_SECRET not found in .env. Exiting.")
    elif not config.GUILD_ID or not config.VERIFY_CHANNEL_ID:
        logging.error("GUILD_ID or VERIFY_CHANNEL_ID not found in .env. Exiting.")
    else:
        bot.run(config.DISCORD_BOT_TOKEN)