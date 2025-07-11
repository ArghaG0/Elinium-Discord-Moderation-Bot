# **Elinium**

Elinium is a dedicated Discord bot focused on **moderation**, providing server administrators with a robust set of tools to manage and secure their communities effectively. It combines powerful automoderation features with essential moderation commands and anonymous confession functionality.

## **Features**

* **Comprehensive Moderation Commands:**  
  * eli warn \<@user\> \[reason\]: Issue warnings to members.  
  * eli warnings \<@user\>: View a member's warning history.  
  * eli clearwarnings \<@user\> \[num\_or\_index\]: Clear all, a specific, or a number of recent warnings for a member.  
  * eli kick \<@user\> \[reason\]: Remove members from the server.  
  * eli ban \<@user\> \[reason\]: Permanently ban members.  
  * eli unban \<user\_id\> \[reason\]: Unban users by their Discord ID.  
  * eli purge \<amount\>: Delete a specified number of messages from the channel.  
  * eli mute \<@user\> \<duration\> \[reason\]: Temporarily restrict members from sending messages (uses Discord's native timeout). Duration examples: 30s, 5m, 1h, 2d, 1w.  
  * eli unmute \<@user\> \[reason\]: Remove timeout from a member.  
  * eli setmodlogchannel \<\#channel\>: Designate a channel for all moderation actions to be logged.  
* **Automoderation System:**  
  * Automatically deletes messages containing blacklisted words.  
  * Automatically deletes messages containing blacklisted links.  
* **Blacklist Management (Prefix Commands):**  
  * eli blacklist addword \<word(s)\>: Add one or more words to the server's blacklist.  
  * eli blacklist removeword \<word(s)\>: Remove one or more words from the server's blacklist.  
  * eli blacklist listwords: List all currently blacklisted words.  
  * eli blacklist addlink \<link(s)\>: Add one or more links to the server's blacklist.  
  * eli blacklist removelink \<link(s)\>: Remove one or more links from the server's blacklist.  
  * eli blacklist listlinks: List all currently blacklisted links.  
* **Anonymous Confessions (Slash Commands):**  
  * /setconfessionchannel \<channel\>: Admins can set a dedicated channel where anonymous confessions will be sent.  
  * /confess \<message\>: Users can send anonymous messages to the designated confession channel.  
* **Interactive Responses:**  
  * Elinium responds to common greetings and phrases, adding a touch of personality.

## **Getting Started**

Follow these steps to get your own Elinium instance running.

### **Prerequisites**

* **Python 3.13.5:** Download from [python.org](https://www.python.org/downloads/).  
* **pip:** Python's package installer (usually comes with Python).  
* **Git:** For cloning the repository.  
* **A Discord Bot Token:**  
  1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).  
  2. Create a new application or select an existing one.  
  3. Navigate to the "Bot" tab and click "Add Bot."  
  4. Under "Privileged Gateway Intents," ensure **MESSAGE CONTENT INTENT** and **MEMBERS INTENT** are **enabled**.  
  5. Copy your bot's **TOKEN**. **Keep this token strictly confidential\!**  
* **Bot Permissions:**  
  1. In the Developer Portal, go to "OAuth2" \-\> "URL Generator".  
  2. Under "SCOPES," select bot and **applications.commands**.  
  3. Under "BOT PERMISSIONS," select the necessary permissions. For full functionality, Administrator is simplest for testing, but for production, consider specific permissions like Manage Channels, Kick Members, Ban Members, Moderate Members, Send Messages, Read Message History, Manage Messages.  
  4. Generate the invite URL and invite the bot to your desired Discord server.

### **Installation**

1. **Clone the repository:**  
   git clone https://github.com/YOUR\_USERNAME/elinium-bot.git \# Replace with your actual repo URL  
   cd elinium-bot

2. **Create a virtual environment (highly recommended):**  
   python \-m venv .venv  
   \# On Windows:  
   .\\.venv\\Scripts\\activate  
   \# On macOS/Linux:  
   source ./.venv/bin/activate

3. **Install dependencies:**  
   pip install \-r requirements.txt

## **Configuration**

Elinium relies on environment variables for sensitive data and dynamic settings.

### **Environment Variables**

You **must** set the following environment variables. When running locally, you can set these in your terminal session. When deploying to a hosting platform like Replit, you will set them in the platform's dashboard/secrets.

* **BOT\_TOKEN**: Your Discord bot's secret token.  
  * *Example:* MTE1NDcxMjM0NTY3ODkwMTIzNDU.ABCDEF.abcdefghijklmnop  
* **EMOJIS**: A JSON string containing the mapping for your custom Discord emojis. Elinium uses these specific emojis for its responses and embeds.  
  * **CRITICAL NOTE ON CUSTOM EMOJIS:**  
    * These emojis (\<:name:ID\> or \<a:name:ID\>) are **custom server emojis**.  
    * For them to display correctly, your bot **must be in a Discord server that has these exact emojis uploaded and available**.  
    * If the bot is not in such a server, or if these emojis are removed, they will appear as plain text (e.g., :26985whitecrown:) or broken images.  
    * If you deploy this bot to a server without these specific emojis, you will need to **replace the values in this JSON string with standard Unicode emojis** (e.g., "CROWN": "👑", "SPARKLE": "✨") for them to display universally.  
  * *Example JSON String (copy this exactly for the environment variable):*  
    {  
      "CROWN": "\<:26985whitecrown:1392780685592231936\>",  
      "HEART": "\<:32562pinkheart:1392780764835217408\>",  
      "SPARKLE": "\<a:80524pinkstars:1392781611623514173\>",  
      "RIBBON": "\<:22499bow:1392780501886177380\>",  
      "FLOWER": "\<:CherryBlossom:1392784047234748417\>",  
      "STAR": "\<a:Pinkstar:1392784692138217543\>",  
      "MANYBUTTERFLIES": "\<a:65954pinkbutterflies:1392780618018066512\>",  
      "BUTTERFLY": "\<a:95526butterflypink:1392781803093233765\>",  
      "ERROR": "❌"  
    }

## **Data Files**

Elinium stores its dynamic data in local JSON files:

* warnings.json: Stores member warning records.  
* blacklists.json: Stores server-specific blacklisted words and links.  
* confession\_channels.json: Stores the configured anonymous confession channel ID for each guild.  
* modlog\_settings.json: Stores the designated moderation log channel ID for each guild.

CRITICAL WARNING ABOUT DATA PERSISTENCE  
When hosting Elinium on platforms like Replit, these local JSON files are stored on an ephemeral filesystem. This means that all data stored in these files will be completely wiped and reset to their initial empty state every time your bot's service restarts or is redeployed (e.g., after a code change or platform update). This includes:

* All warnings issued.  
* All blacklisted words and links.  
* All configured confession channels.  
* All configured modlog channels.

**This setup is NOT suitable for a production bot where data persistence is required.** For a truly persistent and reliable bot, you would need to migrate to a dedicated database solution (e.g., PostgreSQL, MongoDB, Google Firestore, etc.).

## **Running Elinium**

### **Running Locally**

1. **Activate your virtual environment.**  
2. **Set the required environment variables** (BOT\_TOKEN, EMOJIS) in your terminal session.  
3. **Run the bot:**  
   python main.py

### **Hosting on Replit**

Replit is an online IDE and hosting platform that can run Python Discord bots.

1. **Prepare your code:**  
   * Ensure requirements.txt is updated with all your bot's dependencies (pip freeze \> requirements.txt in your local environment).  
   * **Remove any aiohttp or Flask related web server code** from your main.py file. Elinium's main.py should now only contain the Discord bot logic.  
   * Remove any Procfile if you created one for other platforms.  
2. **Commit and Push** all your code changes to your GitHub/GitLab repository.  
3. **Create a new Repl:**  
   * Go to [Replit.com](https://replit.com/) and log in.  
   * Click "Create Repl" (usually a \+ button).  
   * Choose "Import from GitHub".  
   * Paste the URL of your Elinium bot's GitHub repository.  
   * Select "Python" as the language.  
   * Click "Import Repl".  
4. **Set Secrets:**  
   * Once the Repl is created, go to the "Secrets" tab (looks like a lock icon) in the left sidebar.  
   * Click "New Secret".  
   * Add your environment variables:  
     * **Key:** BOT\_TOKEN  
     * **Value:** Your Discord bot's token.  
     * **Key:** EMOJIS  
     * **Value:** Your custom emojis as the JSON string provided in the "Environment Variables" section above.  
5. **Run the Bot:**  
   * Replit will automatically detect and install dependencies from requirements.txt.  
   * It will then attempt to run your main.py file.  
   * To keep your bot running 24/7, enable the "Always On" feature in Replit's "Uptime" section (usually found under the "Tools" tab or by clicking the "Run" button dropdown).  
   * **Note on "Always On":** While Replit's "Always On" feature aims to keep your bot active, sometimes it can be unreliable for critical 24/7 operation. For maximum uptime, some users still combine Replit with an external uptime monitor (like UptimeRobot) that pings a simple web server running within the Repl. If you find your bot frequently going offline, consider adding a basic Flask or http.server web server to your main.py (running in a separate thread) and pinging its public URL.

## **License**

This project is licensed under the MIT License \- see the [LICENSE](https://www.google.com/search?q=LICENSE) file for details.

## **Acknowledgements**

* [discord.py](https://discordpy.readthedocs.io/en/stable/): The powerful Python library used to build this bot.  
* [Replit](https://replit.com/): For providing an online IDE and hosting environment.  
* [UptimeRobot](https://uptimerobot.com/): (Optional, if using external uptime monitoring with Replit).