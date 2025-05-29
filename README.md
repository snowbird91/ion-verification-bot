# TJHSST Discord ION Verification Bot

This project is a Discord bot designed to verify TJHSST students using their ION accounts via OAuth2. Once verified, the bot assigns roles based on their class year (e.g., 2025, 2026) and can remove a designated "unverified" role. This helps manage roles and permissions within a TJHSST-related Discord server.

## Features

-   **ION OAuth Verification:** Securely verifies users through the official TJHSST ION portal.
-   **Automated Role Management:**
    -   Assigns specific roles based on the user's ION-derived class year.
    -   Removes a pre-configured "unverified" role upon successful verification.
-   **Interactive Button:** Users start the verification process by clicking a "Verify" button on a message posted by the bot.
-   **Configurable:** Roles, channel IDs, and OAuth credentials are managed through an environment file for easy setup.

## Prerequisites

-   Python 3.10+
-   `pip` (Python package installer)
-   A Discord Bot Application (see [Step 2](#step-2-create-a-discord-bot-application))
-   An ION OAuth Application (see [Step 3](#step-3-create-an-ion-oauth-application))
-   (Optional for public access) `ngrok` or a similar tunneling service if running the web server component locally and needing external access.

## Setup Instructions

### Step 1: Clone the Repository

Clone this repository to your local machine or server:
```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY_NAME.git
cd YOUR_REPOSITORY_NAME
