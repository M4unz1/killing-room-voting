# Community Content 0.1.0 — Alpha

[Deutsche Anleitung](README.md)

Optional content pack for the analyzed Killing Room build, Unity 5.3.4f1.
It runs through BepInEx 5.4.23.6. Installation does not modify the game DLL or
the existing voting patch.

**Validation:** Compiled against the actual supplied game assemblies. Rule and
installer tests and static game-method checks pass. A Windows game launch has
not yet been tested here. Start with a fresh test run.

## Install

1. Extract the complete **Community Content Alpha package**. A GitHub source ZIP
   alone does not contain the compiled plugin DLL.
2. Close Killing Room. Python 3.10 or newer is required for the installer; it is
   not required by the content plugin while playing.
3. Run `INSTALLIEREN.bat` and select the installed `KillingRoom.exe`. The installer
   detects x86/x64, downloads the pinned official BepInEx release and verifies
   hashes before writing files. Internet access is needed for this step.
4. Launch the game. **F6 in the main menu** cycles the next new run's challenge.
   **F8** toggles the content HUD and elite labels.
5. For audience voting, continue using your existing server/PC relay. This pack
   does not need another local server.

A different existing loader or BepInEx version is preserved. If you already have
a compatible mod setup, install the plugin manually under
`BepInEx/plugins/KillingRoomCommunity/` after checking runtime compatibility.

## Challenges

| Selection | Rules |
| --- | --- |
| `Off` | No additional challenge. Items and enemy variants remain enabled. |
| `GlassCannon` | +35% direct player damage; +50% incoming damage. |
| `ArmsRoulette` | After clearing a combat room, switch to another owned weapon, including melee. A single available weapon stays selected. |
| `Showtime` | Clear ordinary combat rooms within 45 seconds by default. Overtime means +25% incoming damage until that room clears. Quick clears add 2% direct damage each, capped at 20% for the run. Boss and puzzle rooms are not timed. |
| `ChaosBroadcast` | A seeded modifier per floor: Turbo (+12% player movement and +15% ordinary enemy movement), Iron Broadcast (−15% incoming damage and +25% ordinary enemy health), or Glass Air (+20% direct damage and +15% incoming damage). |

The selection locks at the first combat room. Saved content runs keep their
challenge when resumed.

## Items

These have unique identifiers, names and effects, with reused game icons. They
join native loot and voting pools; random selection does not guarantee that all
six appear in a particular run.

| Item | Effect |
| --- | --- |
| Adrenaline Battery | +15% movement speed for 8 seconds after clearing a combat room. |
| Echo Magazine | Every sixth eligible standard gun volley triggers one free extra volley. Melee and special projectile implementations are excluded. |
| Emergency Relay | After surviving a hit at 25% health or less, take 50% less damage for 4 seconds. Cooldown: 45 seconds. Does not revive dead players. |
| Overheated Relay | +12% direct damage, but +15% incoming damage. A cursed voting item with a tradeoff. |
| Lead Boots | −8% of the speed-stat range and +4 defense points. |
| Static Coil | Each cleared combat room drains 5% of maximum armour, without draining health. |

For friendly names in the viewer browser, server operators can merge the six
entries in `content-metadata.json` into their existing `items.json`, then
restart the server. Preserve custom entries. This source branch already includes
the six labels in the default file. The voting protocol is unchanged, so clients
with and without this pack can share a server.

## Enemy variants

Default chance: 18% per eligible ordinary enemy.

| Role | Behavior |
| --- | --- |
| Sprinter | +35% movement speed and −20% health. |
| Juggernaut | +80% health, 20% damage reduction and −25% movement speed. |
| Medic | +15% health; every 4 seconds heals nearby living ordinary allies in the same room by 6% of their maximum health. No resurrection or boss healing. |

These reuse existing models. New 3D models are not included. Bosses, snowmen
and specialized AI classes are excluded from the first alpha. No extra enemies
are spawned and native room counters are preserved.

## Configuration

After the first launch, edit
`BepInEx/config/m4unz1.killingroom.content.cfg` with the game closed, then restart.

- `NextRun`: `Off`, `GlassCannon`, `ArmsRoulette`, `Showtime`, `ChaosBroadcast`.
- `ShowtimeSeconds`: 10–300; default 45.
- `GenerateNewItems`: Add items to new loot/votes. False prevents new generation;
  existing saved items stay registered.
- `EnableVariants`: Enable new enemy roles.
- `VariantChance`: 0–0.5; default 0.18.
- `ShowHud`: Show the status HUD and elite labels.
- `EnableItemGrantKey`: Optional testing aid. When true, **F7** grants the three
  positive items. Disabled by default.

## Saves and removal

On the first plugin launch, an existing `Save.json` is copied once to
`Save.json.krce-original.bak` beside it. If no save exists at that first launch,
this is recorded; a later modded save is not presented as the initial backup.

`Save.json.krce-state` stores the challenge, RNG, item progress and remaining
effect durations. It is bound to the corresponding native save's hash. The game
still writes its own save; save encryption is unchanged.

**Resuming a save containing new item identifiers requires this plugin.** Finish
or discard that run, or restore the initial backup before removing the plugin.
Keep the backup.

With the game closed, disable only
`BepInEx/plugins/KillingRoomCommunity/KillingRoomCommunity.Content.dll` by moving
it outside `plugins`, for example to `BepInEx/disabled/`. Preserve other mods,
BepInEx and the working voting patch.

## First in-game checks

1. Start a fresh run and check F6/F8 and the menus.
2. Enter and clear an ordinary combat room with Showtime selected.
3. Check elite labels, room completion and doors.
4. Optionally enable F7 and check the item UI, Echo Magazine and Adrenaline Battery.
5. Save at a normal game save point, restart and resume. Check the challenge and items.
6. Try an online vote involving a new item. Report the action and relevant
   `BepInEx/LogOutput.log` messages if something fails.

## Development

`build.py` needs a .NET SDK, .NET 3.5 reference assemblies and external game and
BepInEx references. See `build.py --help`. Do not distribute original game DLLs
or decompiled game implementations.

Rule tests: `dotnet run --project tests/RulesTests.csproj -c Release`.
Installer tests: `python -m unittest discover -s tests -p 'test_*.py' -v`.
Static ABI audit: `python tools/verify_game_api.py /path/to/Assembly-CSharp.dll`.

References: [BepInEx 5.4.23.6](https://github.com/BepInEx/BepInEx/releases/tag/v5.4.23.6),
[plugin development](https://docs.bepinex.dev/v5.4.11/articles/dev_guide/plugin_tutorial/1_setup.html).
