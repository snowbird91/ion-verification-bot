import discord
from discord.ext import commands
from discord.ui import Button, View
import config 
import logging

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.message_content = True 
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

class VerificationView(View):
    def __init__(self, base_url: str, guild_id: int):
        super().__init__(timeout=None)
        self.base_url = base_url
        self.guild_id = guild_id

        verify_button = Button(label="Verify with ION", style=discord.ButtonStyle.green, custom_id="verify_ion_button")
        verify_button.callback = self.verify_button_callback
        self.add_item(verify_button)

    async def verify_button_callback(self, interaction: discord.Interaction):
        verification_start_url = f"{self.base_url}/start-verify?user_id={interaction.user.id}&guild_id={self.guild_id}"
        
        logging.info(f"User {interaction.user.name} ({interaction.user.id}) clicked verify. Sending link: {verification_start_url}")
        
        await interaction.response.send_message(
            f"Please click this link to verify with your TJHSST ION account: {verification_start_url}\n"
            "Make sure you are logged into the correct ION account in your browser.",
            ephemeral=True
        )

@bot.event
async def on_ready():
    logging.info(f'{bot.user.name} has connected to Discord!')
    
    if not config.GUILD_ID or not isinstance(config.GUILD_ID, int):
        logging.error(f"GUILD_ID (current: {config.GUILD_ID}) is not configured correctly in config.py or .env. Bot cannot proceed.")
        return
    if not config.VERIFY_CHANNEL_ID or not isinstance(config.VERIFY_CHANNEL_ID, int):
        logging.error(f"VERIFY_CHANNEL_ID (current: {config.VERIFY_CHANNEL_ID}) is not configured correctly. Bot cannot proceed.")
        return
    if not config.FLASK_BASE_URL:
        logging.error(f"FLASK_BASE_URL (current: {config.FLASK_BASE_URL}) is not configured. Bot cannot proceed.")
        return

    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        logging.error(f"Bot could not find Guild with ID: {config.GUILD_ID}. Ensure it's correct and bot is in the server.")
        return

    channel = guild.get_channel(config.VERIFY_CHANNEL_ID)
    if not channel:
        logging.error(f"Bot could not find Channel with ID: {config.VERIFY_CHANNEL_ID} in guild {guild.name}.")
        return

    verification_view = VerificationView(base_url=config.FLASK_BASE_URL, guild_id=config.GUILD_ID)

    bot.add_view(verification_view)
    logging.info("VerificationView (re-)registered with the bot to handle button interactions.")

    message_found_in_history = False
    try:
        async for msg in channel.history(limit=100):
            if msg.author == bot.user and msg.components:
                for row in msg.components:
                    for component in row.children:
                        if isinstance(component, Button) and component.custom_id == "verify_ion_button":
                            logging.info(f"Found existing verification message (ID: {msg.id}) in channel {channel.name}'s recent history.")
                            message_found_in_history = True
                            break 
                    if message_found_in_history: break
                if message_found_in_history: break
    except discord.Forbidden:
        logging.error(f"Bot lacks permission to read message history in channel {channel.name} ({channel.id}). Cannot check for existing message.")
        return
    except Exception as e:
        logging.error(f"Error while checking message history: {e}")
        return

    if not message_found_in_history:
        logging.info(f"No existing verification message found in the last 100 messages. Sending new one to channel: {channel.name}")
        try:
            await channel.send(
                "**TJHSST Student Verification**\n\n"
                "Click the button below to verify your identity using your TJHSST ION account. "
                "This will assign you the appropriate class year role and remove any unverified roles.",
                view=verification_view
            )
            logging.info("New verification message sent.")
        except discord.Forbidden:
            logging.error(f"Bot does not have permission to send messages in channel {channel.name} ({channel.id}).")
        except Exception as e:
            logging.error(f"Failed to send new verification message: {e}")
    else:
        logging.info("Existing verification message confirmed in recent history. Bot will use it.")


if __name__ == '__main__':
    if not config.DISCORD_BOT_TOKEN:
        logging.error("DISCORD_BOT_TOKEN not found. Please set it in your .env file or environment variables.")
    elif not all([config.ION_CLIENT_ID, config.ION_CLIENT_SECRET, config.FLASK_BASE_URL, 
                  config.ION_REDIRECT_URI, config.GUILD_ID, config.VERIFY_CHANNEL_ID]):
        logging.error("One or more required configuration variables (ION_CLIENT_ID, ION_CLIENT_SECRET, FLASK_BASE_URL, ION_REDIRECT_URI, GUILD_ID, VERIFY_CHANNEL_ID) are missing.")
    else:
        bot.run(config.DISCORD_BOT_TOKEN)
