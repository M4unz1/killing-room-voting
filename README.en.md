# Killing Room Community Voting

**Optional content pack:** [Community Content Alpha](content-expansion/README.en.md)
adds four challenges, six items and three enemy variants. It installs separately
and still needs a Windows in-game test.

**Version 0.2.1 · [Deutsch](README.md) · English**

Let viewers vote in Killing Room again. They use a link or Discord to choose
rewards and punishments delivered to the game. This mod replaces the discontinued
voting service with a server you can host yourself.

Several players can share one server at the same time. Each has separate votes
and viewer links. The game itself remains single-player.

**New: API keys are automatic.** Enter the server address. On first connection,
your PC generates its own key and registers it with the server. You do not need
to request a key from the operator or enter one manually.

- **Want to play?** Start with [Set up your gaming PC](#set-up-your-gaming-pc).
- **Want to host?** Follow [Set up your own server](#set-up-your-own-server).
- **Just watching?** Open the player's viewer link. You do not need the mod.

## Set up your gaming PC

You need **Windows**, **Killing Room**, **Python 3.10 or newer**, and the HTTPS
address of a running voting server, such as `https://vote.example.com`.
Replace example addresses in this guide with the real address.

### 1. Download the project

On GitHub, select **Code → Download ZIP** and extract the complete archive.
Keep all project files together in the extracted folder.

### 2. Enter the server address

Double-click `EINSTELLUNGEN_BEARBEITEN.bat`. It opens `settings.json`, creating
your copy from the template if needed.

Change these values in the `client` section, then save the file:

| Setting | What to enter |
| --- | --- |
| `server_url` | Your voting server's HTTPS address, without an extra path. |
| `player_name` | Optional name for your registration. You can leave it empty. |

Leave `game_dll` and `game_executable` empty for now. Keep the other sections.
The voting page will use the player name sent by the game.

### 3. Install the patch

Close Killing Room and double-click `EINSTELLUNGEN_ANWENDEN.bat`.

- Your API key is generated, saved, and registered automatically.
- Select `Assembly-CSharp.dll` from the game's `<Game>_Data/Managed/` folder.
- The installer backs up the original file and applies the matching patch.

The game executable is normally detected automatically. If `game_executable`
stays empty, enter the full path to the Killing Room `.exe` in that field.
Unknown DLL versions or unrelated modifications are rejected.

### 4. Connect and play

1. Double-click `3_SPIEL_PC_VERBINDEN.bat` and keep its window open.
2. Launch Killing Room and generate the audience URL in the game.
3. Share the resulting HTTPS link with your viewers.
4. Start a run. The four voting options appear automatically.

Viewers only need that link. The game collects votes at the end of the level.

> Run either `3_SPIEL_PC_VERBINDEN.bat` **or** `2_SERVER_STARTEN.bat` on your PC.
> Use **3** for a shared public server. **2** starts the separate local test mode.

### Windows launcher names

The files keep their German names in both language versions:

| File | Purpose |
| --- | --- |
| `EINSTELLUNGEN_BEARBEITEN.bat` | Open or create your settings file. |
| `EINSTELLUNGEN_ANWENDEN.bat` | Register this PC, retrieve settings, and apply the patch. |
| `3_SPIEL_PC_VERBINDEN.bat` | Connect to the shared server. |
| `2_SERVER_STARTEN.bat` | Start a standalone local server. |
| `1_PATCH_INSTALLIEREN.bat` | Alternative patch installer using your settings. |
| `ORIGINAL_WIEDERHERSTELLEN.bat` | Restore the original game DLL. |

## Change settings

The operator changes shared server settings in the server's `settings.json`,
then restarts the app.

| Setting | Meaning | Default |
| --- | --- | --- |
| `minimum_votes` | Votes needed before an item is awarded. Allowed: 1–127. | `1` |
| `connection_timeout_seconds` | Close a session after this many seconds without a heartbeat. Allowed: 5–86400; `0` disables it. | `120` |
| `stats.public` | Show the public statistics page. | `true` |

After changing the required votes: **Close the game and run
`EINSTELLUNGEN_ANWENDEN.bat` again on the gaming PC.** A run that has already
started keeps its previous vote requirement.

### What happens when someone stops playing?

While the game runs, the PC sends regular heartbeats. If the game or relay
window closes, the server ends that session after the timeout. Voting closes
and the viewer page stops polling. Other players continue normally, and stored
statistics remain available. A pause in a running game alone does not cause a timeout.

## Set up your own server

This section is for the **operator**. Other players do not need these steps.

You need a Linux server with **Python 3**, **Docker Compose**, and a domain or
subdomain pointing to the host. Ports **80 and 443** must be reachable so Caddy
can provide HTTPS.

### 1. Prepare files and hostname

Copy the project to the server and run this from its folder:

```bash
python3 setup_server.py vote.example.com
```

Replace the example hostname. This creates the configuration files and the
`seed/` folder. An existing `settings.env` is not overwritten.

### 2. Start the server

```bash
docker compose --env-file settings.env up -d --build
```

Give players **only the server address**. Their keys are registered automatically
on first connection. You do not need to distribute key files.

- Home page: `https://YOUR-DOMAIN`
- Shared statistics: `https://YOUR-DOMAIN/stats`
- Viewer link: Generated by the game for each run.

### 3. Manage the server

View logs:

```bash
docker compose --env-file settings.env logs --tail 100 app
```

Restart after changing `settings.json` or `clients.json`:

```bash
docker compose --env-file settings.env restart app
```

**Keep during updates:** `settings.json`, `settings.env`, `clients.json`,
`client_keys/`, your own `items.json`, and Docker data volumes. The database is
stored in the `kr_data` volume.

Optional first migration: Stop the old local server and copy its
`kr_voting.sqlite3` to `seed/kr_voting.sqlite3`. It is imported only if the data
volume is still empty.

## Automatic keys and individual players

Each gaming PC saves a separate key per server in `client_keys/`. Keep these files
private and preserve them during updates. The server stores only hashes.
Restarts and timeouts reuse the same key. Losing the local key file creates
a new player identity on the next connection.

The `registration` section in the server's `settings.json` controls new players:

| Setting | Meaning | Default |
| --- | --- | --- |
| `enabled` | Automatically accept new gaming PCs. | `true` |
| `per_hour` | Maximum new registrations in a rolling hour, across the whole server. | `60` |
| `max_clients` | Maximum automatically registered identities in total. | `10000` |

Existing keys keep working when registration is closed or a limit is reached.
Repeating registration with the same key does not allocate another player.

For **individual vote requirements, Discord destinations, or revocation**, use
the player ID shown in the client console or server log in `clients.json`:

```json
{
  "clients": [
    {
      "id": "auto_REPLACE_WITH_THE_REAL_PLAYER_ID",
      "minimum_votes": 3,
      "discord_channel_id": "123456789",
      "discord_guild_id": "987654321",
      "enabled": true
    }
  ]
}
```

Replace the ID and Discord numbers. Add further entries for other players.
Omit the Discord fields if unused. Set `enabled` to `false` to revoke that key,
including repeat registration attempts. Restart the server after changes.

Existing manual keys still work. Operators who keep automatic registration
closed can optionally create keys in advance with `clients.py`.

## Enable Discord

1. Create a bot in the [Discord Developer Portal](https://discord.com/developers/applications).
   Save its token as `DISCORD_BOT_TOKEN` in the server's `settings.env`.
2. Invite the bot with the `bot` and `applications.commands` scopes. In the voting
   channel it needs View Channel, Send Messages, Embed Links, and Read Message
   History. Privileged intents are not needed.
3. In the server's `settings.json`, set `enabled` to `true` in the `discord` section.
4. Add the player's channel and guild IDs in `clients.json` (example above),
   then restart the app container.

The bot shows four voting buttons and closes them after the result is collected.
`/krlink` shows the channel's viewer link; `/krstats` shows boss statistics.
Different players can use different channels.

Each browser profile and Discord account gets one changeable vote. Both methods
contribute to the same total. Without Discord sign-in on the website, one person
can vote through both methods.

## Common questions

**Why is the voting page empty?**

Open the viewer link generated by the game and start a level. The game sends
the four candidates when the level starts.

**Why am I not receiving items?**

Check the patch, the open relay window, and the required vote count. After
changing the count, close the game and apply the patch again.

**Registration was rejected. What should I do?**

Try again later if a quota was reached. Ask the operator if registration is closed
or your key was disabled. Keep the saved key.

**What does the boss percentage mean?**

It compares wins with the boss wins and deaths recorded by this server.
Historical data from the discontinued worldwide service is not included.
You can add item display names in `items.json`.

**How do I remove the patch?**

Close the game and run `ORIGINAL_WIEDERHERSTELLEN.bat`. The backup file
`Assembly-CSharp.dll.kr-original.bak` must still exist.

## Development status

The local in-game item award was confirmed with version 0.1.1. HTTP tests cover
the game protocol, concurrent players, votes, statistics, automatic registration,
restarts, revoked keys, and timeouts. All 127 patch variants were checked at the
IL level. Discord has been tested offline so far.

The Windows process monitor, higher vote requirements in the actual game, live
Discord connectivity, and HTTPS on the target server still need practical testing.
A full Docker deployment test was not possible in the development environment.

Run tests:

```bash
python3 -m pip install -r requirements-discord.txt
python3 -m unittest discover -s tests -v
```

Original game DLLs are not included. Historical protocol notes are in
[`docs/`](docs/). Additional references: [discord.py](https://discordpy.readthedocs.io/en/stable/interactions/api.html)
and [Caddy](https://caddyserver.com/docs/quick-starts/reverse-proxy).
