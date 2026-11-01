# Killing Room Community Voting 0.2

**Sprache:** Deutsch · [English](README.en.md)

Die funktionierende lokale Wiederherstellung wird um einen gemeinsamen Server,
Discord-Abstimmungen, Statistiken, einstellbare Mindeststimmen und Sitzungs-Timeouts
erweitert. Der zentrale Server ist für mehrere gleichzeitig spielende Personen
vorbereitet. Er wird separat auf einem Linux-Server mit Docker betrieben.

## Aufbau

- **Spiel-PC:** Killing Room mit dem vorhandenen DLL-Patch und `bridge.py` auf
  `127.0.0.1:8765`. Jeder Spieler verwendet seinen eigenen API-Schlüssel.
- **Zentraler Server:** Sitzungen, Stimmen, gemeinsame Boss-Statistik und optional
  ein Discord-Bot. Spielzugriffe sind mit Spielerschlüsseln geschützt.
- **Zuschauer:** öffentlicher HTTPS-Link je Spielrunde oder Discord-Knöpfe.
- **Trennung:** Ein Schlüssel kann keine fremde Spielrunde steuern oder deren
  Lebenszeichen senden. Stimmen sind je Spielrunde getrennt.

Der Zuschauerlink enthält keinen Spielerschlüssel. Der API-Schlüssel wird nur
zwischen dem eigenen Spiel-PC und dem zentralen Server verwendet.

## Einstellungen

Im GitHub-Checkout liegen die Vorlagen `settings.example.json` und
`clients.example.json`. Auf dem Spiel-PC erstellt `EINSTELLUNGEN_BEARBEITEN.bat`
die persönliche `settings.json` beim ersten Öffnen. Auf dem Server legt
`setup_server.py` die erforderlichen Konfigurationsdateien an. Diese persönlichen
Dateien und `settings.env` sind durch `.gitignore` vom Versionsverlauf ausgeschlossen.

Die bearbeitbare Datei heißt `settings.json`. Beispiel für die wichtigen Werte:

```json
{
  "minimum_votes": 3,
  "connection_timeout_seconds": 120
}
```

Diese beiden Werte in der vorhandenen vollständigen Datei ändern; die übrigen
Blöcke beibehalten. Mindeststimmen: **1 bis 127**. Timeout: **5 bis 86400 Sekunden**,
oder **0** zum Deaktivieren. Änderungen am Server werden nach dessen Neustart
übernommen. Die Mindeststimmen einer gestarteten Spielrunde bleiben konstant.

`clients.json` kann pro Spieler eine abweichende `minimum_votes` festlegen.
Der Spiel-PC liest seinen Wert anhand seines API-Schlüssels vom Server und
passt die DLL vor dem nächsten Spielstart an. Dafür das Spiel beenden und
`EINSTELLUNGEN_ANWENDEN.bat` ausführen. Es gibt weiterhin eine geprüfte Sicherung
`Assembly-CSharp.dll.kr-original.bak` für die Rücksicherung.

`EINSTELLUNGEN_BEARBEITEN.bat` öffnet die JSON-Datei im Editor.

## Zentralen Server vorbereiten

Benötigt werden ein eigener Linux-Server mit Docker Compose und eine Domain
oder Subdomain. Deren DNS-Eintrag muss auf den Server zeigen; Caddy benötigt
die öffentlichen Ports 80 und 443 für HTTPS. Das Paket erstellt oder bucht
keinen Server und verändert keine DNS-Einträge.

1. Dieses Paket in einen neuen Ordner auf dem Server entpacken.
2. Im Paketordner ausführen:

   ```bash
   python3 setup_server.py vote.example.de
   ```

   `vote.example.de` durch die eigene Subdomain ersetzen. Es entstehen
   `settings.env` mit einem zufälligen Standardschlüssel und das Verzeichnis `seed`.
3. Für jeden Spieler einen eigenen Schlüssel erzeugen, auch für dich selbst:

   ```bash
   python3 clients.py "Lars" --minimum-votes 3
   python3 clients.py "Spieler 2" --minimum-votes 5
   ```

   Die zugehörigen Schlüsseldateien liegen unter `client_keys/`. Jede Person
   erhält nur ihre eigene Datei und speichert sie auf dem Spiel-PC als
   `settings.env`. Die Liste `clients.json` enthält nur die Schlüssel-Prüfsummen.
4. Optional vor dem ersten Start: Den bisherigen lokalen Voting-Server stoppen
   und seine `kr_voting.sqlite3` nach `seed/kr_voting.sqlite3` auf dem Server
   kopieren. Beim ersten Start mit leerem Datenvolume wird sie übernommen.
   Ein vorhandenes Server-Datenvolume wird dadurch nicht überschrieben.
5. Starten:

   ```bash
   docker compose --env-file settings.env up -d --build
   ```

   Caddy leitet HTTPS zum internen Server weiter. Die Datenbank liegt dauerhaft
   im Docker-Volume `kr_data`. Die Statistik ist unter `https://vote.example.de/stats`
   erreichbar. Die eigentlichen Zuschauerlinks entstehen beim Spielstart.

Diagnose und Neustart:

```bash
docker compose --env-file settings.env logs --tail 100 app
docker compose --env-file settings.env restart app
```

Nach Änderungen an `settings.json` oder `clients.json` den App-Container neu
starten. Damit werden auch neue Discord-Server registriert. Beim Aktualisieren
eigene `settings.json`, `settings.env`, `clients.json`, `client_keys/`, `items.json`
und Datenvolumes aufbewahren.

## Jeden Spiel-PC verbinden

1. Paket vollständig auf den Windows-PC entpacken. Python 3.10 oder neuer ist
   erforderlich. Der PC-Client benötigt keine zusätzlichen Python-Pakete.
2. Die eigene Schlüsseldatei vom Server als `settings.env` im Paketordner speichern.
3. `EINSTELLUNGEN_BEARBEITEN.bat` öffnen und in `settings.json` unter
   `client.server_url` die HTTPS-Basisadresse eintragen:

   ```json
   "client": {
     "server_url": "https://vote.example.de",
     "game_dll": "",
     "game_executable": ""
   }
   ```

4. Killing Room beenden. `EINSTELLUNGEN_ANWENDEN.bat` starten und die DLL aus dem
   installierten Spiel wählen. Der Installer speichert ihren Pfad und erkennt
   normalerweise auch die zugehörige Spiel-EXE. Falls `game_executable` leer bleibt,
   dort den vollständigen Pfad zur Killing-Room-EXE eintragen.
5. `3_SPIEL_PC_VERBINDEN.bat` starten. Dabei wird die Mindeststimmenzahl mit dem
   zentralen Server abgeglichen. Das Fenster geöffnet lassen.
6. Killing Room starten, Zuschauer-URL erzeugen und den HTTPS-Link teilen.

Auf dem Spiel-PC läuft entweder die lokale Variante `2_SERVER_STARTEN.bat` oder
der Client `3_SPIEL_PC_VERBINDEN.bat`: Beide verwenden den vom DLL-Patch erwarteten
Port 8765. Für den dauerhaften gemeinsamen Server ist der dritte Starter vorgesehen.

## Timeout und Ressourcen

Standard: **120 Sekunden ohne Lebenszeichen**. Der Client sendet spätestens
alle 15 Sekunden ein Lebenszeichen; bei kurzen Timeouts entsprechend häufiger.
Die Erkennung vergleicht unter Windows den Pfad des laufenden Spielprozesses
mit `client.game_executable`. Ein langer Bosskampf oder eine Pause im noch
laufenden Spiel führt dadurch nicht allein zum Timeout.

Wird das Spiel oder der Client beendet, gibt es keine weiteren Lebenszeichen.
Nach Ablauf des Timeouts schließt der Server die Sitzung und ihre Abstimmungen.
Die Bereinigung läuft in Abständen von höchstens fünf Sekunden. Discord-Knöpfe
werden deaktiviert, Browser beenden ihre automatische Abfrage für die beendete
Sitzung. Die anderen Spieler bleiben verbunden. Gesammelte Ergebnisse bleiben
gespeichert. Nach einem Timeout eine neue Spielrunde/Verbindung starten.

Im rein lokalen Modus ist der Timeout nur mit bekanntem Spiel-EXE-Pfad aktiv.
Ohne diesen Pfad bleibt der bisherige lokale Testbetrieb verwendbar.

## Discord aktivieren

Der Bot veröffentlicht pro Abstimmungsrunde eine Nachricht mit den vier Optionen
und aktualisiert diese. Ein erneuter Klick desselben Discord-Kontos ändert seine
Stimme. Nach der Auswertung werden die Knöpfe deaktiviert. Nachrichten-IDs werden
gespeichert, damit ein normaler Bot-Neustart vorhandene Nachrichten weiterverwendet.

1. Im [Discord Developer Portal](https://discord.com/developers/applications) eine
   eigene Anwendung mit Bot erstellen und den Token auf dem Server in
   `settings.env` als `DISCORD_BOT_TOKEN` eintragen. Den Token lokal aufbewahren.
2. Bot mit den Scopes `bot` und `applications.commands` auf die gewünschten
   Discord-Server einladen. Im Abstimmungskanal braucht er Kanalansicht,
   Nachrichten senden, Links einbetten und Nachrichtenverlauf lesen.
   Message-Content- und Members-Intents werden nicht benötigt.
3. In der zentralen `settings.json` `discord.enabled` auf `true` setzen.
4. In `clients.json` beim jeweiligen Spieler `discord_channel_id` und
   `discord_guild_id` ergänzen. Alternativ schon beim Anlegen:

   ```bash
   python3 clients.py "Spieler 3" --minimum-votes 3 --discord-channel 123456789 --discord-guild 987654321
   ```

   Die Zahlen durch echte Kanal- und Server-IDs ersetzen. Die globalen Discord-IDs
   in `settings.json` sind nur für den optionalen Standardschlüssel vorgesehen.
5. App neu starten. `/krstats` zeigt die gemeinsame Boss-Statistik; `/krlink` die
   aktuelle Abstimmung des jeweiligen Kanals. Unterschiedliche Spieler können
   unterschiedliche Kanäle und Discord-Server verwenden.

Browser und Discord zählen in denselben Stimmenpool. Es gibt jeweils eine Stimme
pro Browserprofil beziehungsweise Discord-Konto und Runde. Ohne Discord-Anmeldung
auf der Webseite kann dieselbe Person über beide Wege teilnehmen. Browser-Cookies
sind keine starke Personenidentifikation.

## Statistiken

Erfasst werden Boss-Siege, Niederlagen am Boss, deren Quote, begonnene Spielrunden,
Abstimmungsrunden, Stimmen und beliebte Item-Optionen. Wiederholte Boss-Meldungen
derselben Spielrunde werden dedupliziert. Das Spiel erhält die gemeinsamen
Boss-Zähler über seinen vorhandenen `getBossStat`-Endpunkt.

Die Quote bezieht sich auf die auf diesem Server erfassten Bossausgänge. Es werden
keine alten weltweiten Zahlen erfunden. Bei neuen Bossen fehlen zunächst Daten.
Die Anzeige verwendet Boss-/Levelnummern und Item-Kennungen, bis zusätzliche
Spiel-Assets für Namen und Bilder vorliegen. `items.json` kann wie bisher eigene
Anzeigenamen enthalten. `stats.public=false` schaltet die öffentliche Statistik ab.

## Prüfstand

Die ursprüngliche lokale Item-Vergabe wurde vom Nutzer mit 0.1.1 bestätigt.
Version 0.2 wurde mit lokalen HTTP-Integrationstests geprüft: getrennte Spieler-
schlüssel, parallele Stimmen für getrennte Runden, gemeinsame Boss-Quoten,
authentifizierter PC-Client, Datenbankmigration, Heartbeats, Timeout und echter
Hub-Programmstart einschließlich Bereinigung. Discord-Knöpfe wurden ohne Login
gegen die installierte discord.py-Version getestet. Alle 127 Mindeststimmen-
Varianten wurden als IL geprüft; die bisherigen Werte 1 und 3 behalten ihre Hashes.

Der neue Windows-Prozessmonitor, höhere Mindeststimmen im echten Spiel sowie
Discord-Verbindung und HTTPS-Betrieb auf dem Zielserver müssen noch praktisch
bestätigt werden. In dieser Umgebung ist kein Docker-Daemon verfügbar.

## Quellen der Integrationen

- [Discord: Interactions](https://docs.discord.com/developers/interactions/overview)
- [discord.py: Interactions API](https://discordpy.readthedocs.io/en/stable/interactions/api.html)
- [Caddy: HTTPS-Reverse-Proxy](https://caddyserver.com/docs/quick-starts/reverse-proxy)

Historische Protokollanalyse und Anleitungen der Version 0.1.1 liegen unter `docs/`.
