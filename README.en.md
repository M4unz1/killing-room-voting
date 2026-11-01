# Killing Room Community Voting 0.2

**Language:** [Deutsch](README.md) · English

Restore Killing Room's audience voting using your own server. Version 0.2 adds
a shared multiplayer service, browser and Discord voting, boss statistics,
configurable vote requirements, and session timeouts to the working local prototype.

The game remains single-player. "Multiplayer service" means that several people
can use the same voting server for their separate game runs at the same time.

## How it works

- **Gaming PC:** Killing Room with the supported DLL patch and a local relay,
  `bridge.py`, listening on `127.0.0.1:8765`.
- **Central server:** Runs continuously on a Linux host with Docker, stores votes
  and statistics, and optionally runs the Discord bot.
- **Viewers:** Vote through the unique HTTPS link for a game run or through Discord
  buttons. Viewers do not need the game's API key.
- **Separate players:** Each player receives an individual API key, independent
  sessions, viewer links, and optional Discord channel settings. A player's key
  cannot control or send heartbeats for someone else's sessions.

The API key is used only between a player's local relay and the central server.
The patcher supports the analyzed `Assembly-CSharp.dll` build and checks its hash
before making changes. Original game DLLs are not included in this repository.

## Requirements

- **Gaming PC:** Windows, an installed copy of Killing Room with the supported DLL,
  and Python 3.10 or newer. The relay requires no additional Python packages.
- **Central server:** Linux, Python 3 for the setup commands, Docker Compose, and a
  domain or subdomain pointing to the host. Public ports 80 and 443 must reach Caddy
  so that it can provide HTTPS.

Download or clone this repository and run the commands below from its root folder.

## Configuration

The tracked configuration templates are `settings.example.json` and
`clients.example.json`. Personal copies are called `settings.json` and `clients.json`.
They, the secret file `settings.env`, keys, databases, and logs are covered by
`.gitignore`.

On a gaming PC, `EINSTELLUNGEN_BEARBEITEN.bat` creates `settings.json` from its
template the first time it opens the editor. On the central server,
`setup_server.py` creates the required configuration files.

For example, change these two keys inside the existing complete `settings.json`:

```json
"minimum_votes": 3,
"connection_timeout_seconds": 120
```

Keep the other configuration blocks. This snippet is not a replacement for the
whole file.

- `minimum_votes`: **1–127** votes required before the game awards the voting item.
- `connection_timeout_seconds`: **5–86400** seconds without a heartbeat, or **0**
  to disable expiration.
- `stats.public`: Set to `false` to disable the public statistics page and API.

Restart the central app after editing server settings. A game run keeps the vote
requirement that was active when that run was created. `clients.json` can override
`minimum_votes` for an individual player; otherwise the server default applies.

Before starting the game after a vote-requirement change, run
`EINSTELLUNGEN_ANWENDEN.bat` on the gaming PC. It retrieves that player's setting
and applies the matching DLL patch. The original DLL is retained as
`Assembly-CSharp.dll.kr-original.bak`.

### Windows launchers

The launcher filenames are the same in both language versions:

| File | Purpose |
| --- | --- |
| `1_PATCH_INSTALLIEREN.bat` | Install the patch using the settings file. |
| `EINSTELLUNGEN_BEARBEITEN.bat` | Open or create your settings file. |
| `EINSTELLUNGEN_ANWENDEN.bat` | Apply settings and the corresponding DLL patch. |
| `2_SERVER_STARTEN.bat` | Start the standalone local voting server. |
| `3_SPIEL_PC_VERBINDEN.bat` | Connect this gaming PC to the central server. |
| `ORIGINAL_WIEDERHERSTELLEN.bat` | Restore the original game DLL. |

The local server and the PC relay both use port 8765. Run one of them at a time.
Use the PC relay for the shared, continuously running central server.

## Set up the central server

1. Place the project in a new directory on your Linux server.
2. Prepare the configuration, replacing the sample hostname with your own:

   ```bash
   python3 setup_server.py vote.example.com
   ```

   This creates `settings.env` with a random default API key, the personal JSON
   configuration files if missing, and the `seed/` directory. It does not overwrite
   an existing `settings.env`.
3. Create an individual key for every player, including yourself:

   ```bash
   python3 clients.py "Player One" --minimum-votes 3
   python3 clients.py "Player Two" --minimum-votes 5
   ```

   Each generated key file is placed in `client_keys/`. Give each player only their
   own file; they save it as `settings.env` on their gaming PC. `clients.json`
   stores key hashes rather than the original keys. If `--minimum-votes` is omitted,
   that player uses the server's default vote requirement.
4. Optional, before the first server start: Stop your previous local voting server
   and copy its `kr_voting.sqlite3` to `seed/kr_voting.sqlite3` on the Linux host.
   The app imports this database only when its persistent data volume is empty.
   An existing server database is not replaced.
5. Start the service:

   ```bash
   docker compose --env-file settings.env up -d --build
   ```

   Caddy provides HTTPS and forwards requests to the internal app. SQLite data is
   stored in the persistent `kr_data` Docker volume. The shared statistics page is
   available at `https://vote.example.com/stats`, using your own hostname.
   Viewer links are generated when players connect their game runs.

Inspect logs and restart the app with:

```bash
docker compose --env-file settings.env logs --tail 100 app
docker compose --env-file settings.env restart app
```

Restart the app after changing `settings.json` or `clients.json`. This also registers
commands for newly configured Discord servers. Keep your personal settings,
`settings.env`, `clients.json`, `client_keys/`, `items.json`, and Docker data volumes
when updating the project.

## Connect each gaming PC

1. Extract or clone the complete project on the Windows PC. Install Python 3.10
   or newer if it is not already available.
2. Save the player's own key file from the central server as `settings.env` in
   the project folder.
3. Run `EINSTELLUNGEN_BEARBEITEN.bat`. In `settings.json`, set `client.server_url`
   to your server's HTTPS base address. The client block looks like this:

   ```json
   "client": {
     "server_url": "https://vote.example.com",
     "game_dll": "",
     "game_executable": ""
   }
   ```

   Keep this block inside the complete settings file.
4. Close Killing Room. Run `EINSTELLUNGEN_ANWENDEN.bat` and select
   `Assembly-CSharp.dll` from the installed game's `<Game>_Data/Managed/` folder.
   The installer saves the DLL path and normally detects the corresponding game
   executable. If `game_executable` remains empty, enter the full path to the
   Killing Room `.exe` in that field.
5. Run `3_SPIEL_PC_VERBINDEN.bat`. It reads the player's required vote count from
   the central server and checks the patch. Leave this window running.
6. Launch Killing Room, generate the audience URL, and share its HTTPS link with
   viewers. Start a run; the voting page updates when the game sends its four
   candidate items.

To restore the original game DLL, close the game and run
`ORIGINAL_WIEDERHERSTELLEN.bat`. Keep the original backup file. The patcher refuses
unknown DLL versions or unrelated modifications instead of overwriting them.

## Heartbeats and timeouts

The default timeout is **120 seconds without a heartbeat**. The PC relay sends a
heartbeat at least every 15 seconds while it detects the configured game process.
Shorter timeouts automatically use a shorter heartbeat interval.

On Windows, process detection compares the running executable's full path with
`client.game_executable`. A long fight or a pause in a running game does not by
itself count as a lost connection.

When the game or the relay exits, heartbeats stop. Once the timeout expires, the
server ends that player's session and closes its votes. Cleanup runs at intervals
of no more than five seconds. Discord buttons are disabled, and a viewer page stops
automatically polling an expired session. Other players continue normally, and
recorded statistics remain stored. Start a new game connection after a timeout.

In standalone local mode, automatic timeout handling requires a known game
executable path. Without one, the previous local test mode remains available.

## Enable Discord voting

The bot publishes one message per voting round with the four candidate options
and updates it as votes change. Clicking again with the same Discord account
changes that account's vote. After the round closes, the buttons are disabled.
Message IDs are persisted so a normal bot restart can reuse existing messages.

1. Create your own bot application in the
   [Discord Developer Portal](https://discord.com/developers/applications).
   On the central server, set `DISCORD_BOT_TOKEN` in `settings.env` to the bot's token.
2. Invite the bot to the relevant Discord servers with the `bot` and
   `applications.commands` scopes. In each voting channel it needs View Channel,
   Send Messages, Embed Links, and Read Message History permissions.
   Message Content and Members privileged intents are not required.
3. Set `discord.enabled` to `true` in the central `settings.json`.
4. Set `discord_channel_id` and `discord_guild_id` on the relevant player's entry
   in `clients.json`. You can also supply them when adding a player:

   ```bash
   python3 clients.py "Player Three" --minimum-votes 3 --discord-channel 123456789 --discord-guild 987654321
   ```

   Replace the numbers with the actual channel and server IDs. Different players
   can use different channels and Discord servers. The global Discord IDs in
   `settings.json` apply only to the optional default API key.
5. Restart the app. `/krstats` displays the shared boss statistics; `/krlink`
   returns the current viewer link for that channel.

Browser and Discord votes share the same voting pool. A browser profile and a
Discord account each get one changeable vote per round. Without Discord sign-in on
the website, a person can participate through both methods. Browser cookies do not
provide strong identification of individual people.

## Statistics

The server records boss wins and deaths, win rates, started game runs, voting
rounds, votes, and popular item options. Repeated boss reports from the same game
run are deduplicated. The game's existing `getBossStat` endpoint receives the
shared boss counters.

Win rates are based on boss outcomes recorded by this server, not the original
service's worldwide historical data. A new server initially has little or no boss
data. Boss/level numbers and item identifiers are shown until additional game
assets provide names and images. `items.json` can supply custom item display names.
Set `stats.public` to `false` to disable public statistics.

## Validation status

The local in-game item award was confirmed with version 0.1.1. Version 0.2 passed
25 automated tests covering separate player keys, concurrent voting for separate
runs, shared boss rates, the authenticated relay, database migration, heartbeats,
timeouts, and startup of the actual hub process with cleanup enabled. Discord
buttons were tested offline against discord.py 2.7.1.

All 127 vote-threshold variants were checked at the IL level; thresholds 1 and 3
retain the previously tested DLL hashes. The new Windows process monitor, higher
thresholds in the actual game, live Discord connectivity, and HTTPS on the target
server still need practical validation. No Docker daemon was available in the
development environment for an end-to-end container deployment test.

Run the test suite from the repository root:

```bash
python3 -m pip install -r requirements-discord.txt
python3 -m unittest discover -s tests -v
```

## Integration references

- [Discord: Interactions](https://docs.discord.com/developers/interactions/overview)
- [discord.py: Interactions API](https://discordpy.readthedocs.io/en/stable/interactions/api.html)
- [Caddy: HTTPS reverse proxy](https://caddyserver.com/docs/quick-starts/reverse-proxy)

Historical protocol notes and version 0.1.1 documentation are in `docs/`.
