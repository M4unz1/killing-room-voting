# Killing Room Community Voting

**Version 0.2.1 · Deutsch · [English](README.en.md)**

Zuschauer können wieder in Killing Room abstimmen: Sie wählen über einen Link
oder in Discord, welche Belohnung oder Bestrafung im Spiel ankommt. Dieser Mod
ersetzt den abgeschalteten Voting-Dienst durch einen eigenen Server.

Mehrere Spieler können denselben Server gleichzeitig nutzen. Jeder hat eigene
Abstimmungen und Zuschauerlinks. Das Spiel selbst bleibt ein Einzelspielerspiel.

**Optionale Inhaltserweiterung:** Die [Community Content Alpha](content-expansion/README.md)
ergänzt vier Challenges, sechs Items und drei Gegnervarianten. Sie wird getrennt
installiert und braucht noch einen Test im Windows-Spiel.

**Neu: API-Schlüssel entstehen automatisch.** Du gibst nur die Serveradresse ein.
Beim ersten Verbinden erzeugt dein PC seinen Schlüssel und registriert ihn am
Server. Du musst keinen Schlüssel anfordern oder von Hand eingeben.

- **Du möchtest spielen?** Starte mit [Spiel-PC einrichten](#spiel-pc-einrichten).
- **Du möchtest einen Server betreiben?** Nutze [Eigenen Server einrichten](#eigenen-server-einrichten).
- **Du möchtest nur abstimmen?** Öffne den Zuschauerlink des Spielers. Du brauchst keinen Mod.

## Spiel-PC einrichten

Du brauchst **Windows**, **Killing Room**, **Python 3.10 oder neuer** und die
HTTPS-Adresse eines laufenden Voting-Servers, zum Beispiel `https://vote.example.de`.
Ersetze Beispieladressen in dieser Anleitung durch deine echte Adresse.

### 1. Projekt herunterladen

Auf GitHub **Code → Download ZIP** wählen und den gesamten Inhalt entpacken.
Alle Dateien müssen zusammen im Projektordner bleiben.

### 2. Serveradresse eintragen

`EINSTELLUNGEN_BEARBEITEN.bat` doppelklicken. Dadurch öffnet sich `settings.json`.
Die Datei wird bei Bedarf automatisch aus der Vorlage erstellt.

Im Abschnitt `client` diese Werte ändern und die Datei speichern:

| Eintrag | Was du einträgst |
| --- | --- |
| `server_url` | Die HTTPS-Adresse deines Voting-Servers, ohne zusätzlichen Pfad. |
| `player_name` | Optional dein Name. Du kannst das Feld auch leer lassen. |

`game_dll` und `game_executable` zunächst leer lassen. Die übrigen Abschnitte behalten.
Der Name auf der Abstimmungsseite wird später vom Spiel übernommen.

### 3. Patch installieren

Killing Room schließen und `EINSTELLUNGEN_ANWENDEN.bat` doppelklicken.

- Dein API-Schlüssel wird automatisch erzeugt, gespeichert und registriert.
- Wähle die `Assembly-CSharp.dll` aus dem Spielordner unter `<Game>_Data/Managed/`.
- Das Programm sichert die Originaldatei und installiert den passenden Patch.

Der Pfad zur Spiel-EXE wird normalerweise automatisch erkannt. Falls
`game_executable` leer bleibt, dort den vollständigen Pfad zur Killing-Room-EXE eintragen.
Unbekannte oder bereits anders veränderte DLL-Versionen werden abgelehnt.

### 4. Verbinden und spielen

1. `3_SPIEL_PC_VERBINDEN.bat` doppelklicken und das Fenster geöffnet lassen.
2. Killing Room starten und im Spiel die Zuschauer-URL erzeugen.
3. Den angezeigten HTTPS-Link an deine Zuschauer weitergeben.
4. Eine Spielrunde starten. Die vier Abstimmungsoptionen erscheinen automatisch.

Zuschauer benötigen nur diesen Link. Die Stimmen werden beim Levelende vom Spiel abgeholt.

> Pro Spiel-PC entweder `3_SPIEL_PC_VERBINDEN.bat` **oder** `2_SERVER_STARTEN.bat`
> ausführen. Für einen gemeinsamen öffentlichen Server ist **3** vorgesehen.
> **2** startet den separaten lokalen Testbetrieb.

## Einstellungen ändern

Die Einstellungen für den gemeinsamen Server ändert der Betreiber in seiner
`settings.json`. Anschließend muss er den Server neu starten.

| Einstellung | Bedeutung | Standard |
| --- | --- | --- |
| `minimum_votes` | Benötigte Stimmen für die Item-Vergabe. Erlaubt: 1–127. | `1` |
| `connection_timeout_seconds` | Sitzung nach so vielen Sekunden ohne Lebenszeichen schließen. Erlaubt: 5–86400; `0` schaltet es ab. | `120` |
| `stats.public` | Öffentliche Statistikseite anzeigen. | `true` |

Nach einer Änderung der benötigten Stimmen: **Spiel schließen und auf dem
Spiel-PC erneut `EINSTELLUNGEN_ANWENDEN.bat` ausführen.** Bereits gestartete
Spielrunden behalten ihre bisherige Stimmenvorgabe.

### Was passiert, wenn jemand aufhört?

Solange das Spiel läuft, sendet der PC regelmäßig ein Lebenszeichen. Wird das
Spiel oder das Verbindungsfenster beendet, endet die Sitzung nach dem Timeout.
Dann schließen die Abstimmungen und die Zuschauerseite hört auf, neue Daten
abzufragen. Andere Spieler können weiter spielen; Statistiken bleiben erhalten.
Eine Pause im laufenden Spiel zählt nicht allein als Verbindungsabbruch.

## Eigenen Server einrichten

Dieser Abschnitt ist für den **Betreiber**. Die anderen Spieler brauchen diese
Schritte nicht auszuführen.

Du brauchst einen Linux-Server mit **Python 3**, **Docker Compose** und einer
Domain oder Subdomain. Deren DNS-Eintrag muss auf den Server zeigen. Die Ports
**80 und 443** müssen erreichbar sein, damit Caddy HTTPS bereitstellen kann.

### 1. Dateien und Domain vorbereiten

Projekt auf den Server kopieren und im Projektordner ausführen:

```bash
python3 setup_server.py vote.example.de
```

Die Beispieladresse ersetzen. Das erstellt die Konfigurationsdateien und den
Ordner `seed/`. Eine vorhandene `settings.env` wird nicht überschrieben.

### 2. Server starten

```bash
docker compose --env-file settings.env up -d --build
```

Die Spieler erhalten jetzt **nur die Serveradresse**. Ihre Schlüssel werden
automatisch beim ersten Verbinden registriert. Du musst keine Schlüssel verteilen.

- Startseite: `https://DEINE-DOMAIN`
- Gemeinsame Statistik: `https://DEINE-DOMAIN/stats`
- Zuschauerlink: Wird für jede Spielrunde vom Spiel erzeugt.

### 3. Server verwalten

Logs anzeigen:

```bash
docker compose --env-file settings.env logs --tail 100 app
```

Nach Änderungen an `settings.json` oder `clients.json` neu starten:

```bash
docker compose --env-file settings.env restart app
```

**Beim Aktualisieren behalten:** `settings.json`, `settings.env`, `clients.json`,
`client_keys/`, eigene `items.json` und die Docker-Datenvolumes. Die Datenbank liegt
im Volume `kr_data`.

Optional beim ersten Umzug: Den bisherigen lokalen Server stoppen und seine
`kr_voting.sqlite3` nach `seed/kr_voting.sqlite3` kopieren. Sie wird nur übernommen,
wenn das Datenvolume noch leer ist.

## Automatische Schlüssel und einzelne Spieler

Der Spiel-PC speichert seinen Schlüssel pro Server unter `client_keys/`. Diese
Dateien privat aufbewahren und beim Update behalten. Der Server speichert nur
Prüfsummen. Neustarts und Timeouts verwenden denselben Schlüssel weiter.
Geht die lokale Schlüsseldatei verloren, entsteht eine neue Spieler-Identität.

In der Serverdatei `settings.json` steuert der Abschnitt `registration` die Aufnahme:

| Eintrag | Bedeutung | Standard |
| --- | --- | --- |
| `enabled` | Neue Spiel-PCs automatisch aufnehmen. | `true` |
| `per_hour` | Höchstens so viele neue Registrierungen in einer rollierenden Stunde, für den gesamten Server. | `60` |
| `max_clients` | Höchstzahl automatisch registrierter Identitäten insgesamt. | `10000` |

Bestehende Schlüssel funktionieren auch bei geschlossener Aufnahme oder erreichtem Limit.
Ein Registrierungsversuch mit demselben Schlüssel erzeugt keinen weiteren Spieler.

Für **eigene Mindeststimmen, Discord-Ziele oder eine Sperre** die Spieler-ID aus
dem Client-Fenster oder Serverlog in `clients.json` eintragen:

```json
{
  "clients": [
    {
      "id": "auto_HIER_DIE_ECHTE_SPIELER_ID",
      "minimum_votes": 3,
      "discord_channel_id": "123456789",
      "discord_guild_id": "987654321",
      "enabled": true
    }
  ]
}
```

ID und Discord-Nummern ersetzen; weitere Spieler als weitere Einträge ergänzen.
Ohne Discord die beiden Discord-Felder weglassen. `enabled: false` sperrt den
Schlüssel auch bei erneuten Registrierungsversuchen. Danach Server neu starten.

Vorhandene manuell vergebene Schlüssel funktionieren weiterhin. Wer die Aufnahme
geschlossen halten möchte, kann mit `clients.py` optional Schlüssel vorab anlegen.

## Discord aktivieren

1. Im [Discord Developer Portal](https://discord.com/developers/applications)
   einen Bot erstellen. Seinen Token auf dem Server in `settings.env` als
   `DISCORD_BOT_TOKEN` speichern.
2. Den Bot mit den Scopes `bot` und `applications.commands` auf deinen Discord-Server
   einladen. Im Voting-Kanal braucht er Kanalansicht, Nachrichten senden, Links
   einbetten und Nachrichtenverlauf lesen. Besondere Intents sind nicht nötig.
3. In der Serverdatei `settings.json` unter `discord` den Wert `enabled` auf `true` setzen.
4. In `clients.json` die Kanal- und Server-ID beim jeweiligen Spieler eintragen
   (Beispiel oben) und den App-Container neu starten.

Der Bot zeigt die vier Optionen als Knöpfe an und schließt sie nach der Auswertung.
`/krlink` zeigt den Zuschauerlink des Kanals; `/krstats` zeigt die Boss-Statistik.
Unterschiedliche Spieler können unterschiedliche Kanäle verwenden.

Pro Browserprofil und pro Discord-Konto gibt es jeweils eine änderbare Stimme.
Beide Wege zählen zusammen. Ohne Discord-Anmeldung auf der Webseite kann dieselbe
Person über beide Wege abstimmen.

## Häufige Fragen

**Warum ist die Abstimmung noch leer?**

Öffne den vom Spiel erzeugten Zuschauerlink und starte einen Level. Erst dann
sendet das Spiel die vier Kandidaten.

**Warum kommen keine Items an?**

Prüfe Patch, geöffnetes Verbindungsfenster und die benötigte Stimmenzahl. Nach
einer Änderung der Stimmenzahl den Patch bei geschlossenem Spiel erneut anwenden.

**Die Registrierung ist abgelehnt. Was tun?**

Bei einem Limit später erneut verbinden. Bei geschlossener Aufnahme oder einer
Sperre den Betreiber fragen. Den gespeicherten Schlüssel behalten.

**Was bedeutet die Boss-Prozentzahl?**

Sie zeigt Siege im Verhältnis zu den auf diesem Server erfassten Boss-Siegen und
Niederlagen. Die Daten des alten weltweiten Dienstes sind nicht enthalten.
Item-Namen kannst du in `items.json` ergänzen.

**Wie entferne ich den Patch?**

Spiel schließen und `ORIGINAL_WIEDERHERSTELLEN.bat` ausführen. Die Sicherung
`Assembly-CSharp.dll.kr-original.bak` muss vorhanden sein.

## Entwicklungsstand

Die lokale Item-Vergabe wurde im Spiel mit Version 0.1.1 bestätigt. HTTP-Tests
prüfen Spielprotokoll, parallele Spieler, Stimmen, Statistik, automatische
Registrierung, Neustarts, Schlüssel-Sperren und Timeouts. Die 127 Patch-Varianten
wurden auf IL-Ebene geprüft; Discord wurde bisher ohne Live-Anmeldung getestet.

Der Windows-Prozessmonitor, höhere Stimmenzahlen im echten Spiel, die Live-Verbindung
zu Discord und HTTPS auf dem Zielserver müssen noch praktisch bestätigt werden.
Ein vollständiger Docker-Test war in der Entwicklungsumgebung nicht möglich.

Tests ausführen:

```bash
python3 -m pip install -r requirements-discord.txt
python3 -m unittest discover -s tests -v
```

Originale Spiel-DLLs sind nicht enthalten. Historische Protokollnotizen liegen
unter [`docs/`](docs/). Weitere Referenzen: [discord.py](https://discordpy.readthedocs.io/en/stable/interactions/api.html)
und [Caddy](https://caddyserver.com/docs/quick-starts/reverse-proxy).
