import os

# Discord Bot Token (replace with your actual token)
TOKEN = os.getenv("discord_token")

# Command prefix
PREFIX = "?"

# List of admin user IDs who can use moderation commands
ADMIN_IDS = [
    974206310058967060,  # Replace with actual admin user IDs
    528858552094425089,
    # Add more admin IDs as needed
]

# Modlog channel ID where moderation actions will be logged
MODLOG_CHANNEL_ID = 1305076688526512200  # Replace with your actual channel ID

# Default reason for moderation actions if none is provided
DEFAULT_REASON = "Breaking server rules"

# Number of warnings before auto-timeout
MAX_WARNINGS = 5

# Auto-timeout duration in seconds (1 day = 86400 seconds)
AUTO_TIMEOUT_DURATION = 86400