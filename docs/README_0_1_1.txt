KILLING ROOM – ZUSCHAUER-VOTING
Lokale Testversion 0.1.1 | 01.11.2026

UPDATE VON VERSION 0.1
1. Spiel beenden und den alten Server mit Strg+C stoppen.
2. Aus diesem Paket nur server.py in deinen bisherigen Voting-Ordner kopieren
   und die alte server.py ersetzen. Die bestehende kr_voting.sqlite3 behalten.
3. Wie bisher 2_SERVER_STARTEN.bat starten. Im Serverfenster muss nun
   Killing Room Voting 0.1.1 bereit stehen.
4. Spiel neu starten, Zuschauerlink erzeugen und einmal abstimmen.
   Nun wird auch jede gespeicherte Stimme im Serverfenster bestaetigt.
Der vorhandene DLL-Patch bleibt verwendbar; erneutes Patchen ist nicht erforderlich.

BEHOBENER FEHLER IN 0.1.1
Das Spiel erhoeht seine Levelnummer bereits vor der Abstimmungsauswertung.
Version 0.1 suchte deshalb beim Ende von Level 1 nach Stimmen fuer Level 2.
Die Auswertung wird jetzt der passenden Kandidaten-Abstimmung zugeordnet.
Wiederholte Anfragen behalten ihre Zuordnung auch nach dem naechsten Level.
Die unveraenderte Nummer beim letzten Level wird ebenfalls beruecksichtigt.

ZIEL
Die alte Zuschauer-Abstimmung mit einem eigenen lokalen Server testen.
Der Patch ist speziell fuer deine hochgeladene Assembly-CSharp.dll erstellt.
Fuer diesen Versuch ist kein Mod-Loader erforderlich.

VORAUSSETZUNGEN
- Killing Room unter Windows, mit der untersuchten DLL-Version.
- Python 3.10 oder neuer. Der Server benoetigt keine zusaetzlichen Pakete.
- Alle Dateien dieses Pakets gemeinsam in einen beschreibbaren Ordner entpacken.

SCHNELLSTART
1. Killing Room beenden.
2. Doppelklick auf 1_PATCH_INSTALLIEREN.bat.
3. Im Dateidialog die Assembly-CSharp.dll im Managed-Ordner des installierten
   Spiels auswaehlen. NICHT eine Kopie aus dem heruntergeladenen Archiv waehlen.
   Den Spielordner findest du in Steam ueber Killing Room > Verwalten >
   Lokale Dateien durchsuchen. Darin: <Spielname>_Data > Managed.
4. Der Installer prueft die Version und sichert die Originaldatei daneben als
   Assembly-CSharp.dll.kr-original.bak. Diese Sicherung aufbewahren.
5. Doppelklick auf 2_SERVER_STARTEN.bat. Das Serverfenster offen lassen.
   Im Browser sollte http://127.0.0.1:8765/ erreichbar sein.
6. Killing Room starten. Im Startmenue die Zuschauer-URL erzeugen und die
   Online-Abstimmung einschalten. Die URL sollte jetzt mit
   http://127.0.0.1:8765/v/ beginnen. Der Server zeigt sie ebenfalls an.
7. Diesen Link im Browser oeffnen und einen neuen Durchlauf beginnen.
   Die Seite aktualisiert sich automatisch, sobald das Spiel die Item-Optionen
   schickt. Eine Option waehlen. Nach Abschluss des Levels die Abstimmung im
   Spiel auswerten lassen und pruefen, ob das entsprechende Item ankommt.

FUER DEN ERSTEN TEST
- Eine einzige Stimme reicht. Normalerweise verlangt das Spiel drei Stimmen.
- Pro Browserprofil und Abstimmung wird eine Stimme gespeichert. Ein erneuter
  Klick aendert die vorhandene Stimme. Nach dem Levelende ist die Wahl geschlossen.
- Fuer einen Test mit drei getrennten Zuschauern verschiedene Browser oder
  getrennte Browserprofile verwenden. Mehrere Tabs teilen dieselbe Stimme.
- Solange keine weiteren Spiel-Assets vorliegen, zeigt die Webseite die echten
  Item-Kennungen aus dem Spiel statt vollstaendiger Namen, Bilder und Beschreibungen.
  Die Zuordnung der Stimmen erfolgt ueber genau diese Kennungen.
- Der Link 127.0.0.1 funktioniert auf dem Spiel-PC. Diese Version richtet keine
  Internetfreigabe fuer Zuschauer ein. Zuerst den Ablauf lokal bestaetigen;
  danach koennen Hosting/Weiterleitung und die oeffentliche Zuschauer-URL folgen.
- Keine spontanen neuen Events: Dieser Prototyp verwendet die vorhandene
  Abstimmung ueber positive und negative Items bei der Levelauswertung.

WIEDER AUF DIE ORIGINALREGEL MIT DREI STIMMEN WECHSELN
Spiel beenden, im Paketordner ein Terminal oeffnen und ausfuehren:
  py -3 patch_game.py --install --minimum-votes 3
Dann dieselbe DLL im Dateidialog auswaehlen. Die Original-Sicherung bleibt erhalten.

ORIGINAL WIEDERHERSTELLEN
Spiel beenden, ORIGINAL_WIEDERHERSTELLEN.bat starten und dieselbe DLL waehlen.
Der Installer prueft die Sicherung vor der Ruecksicherung. Eine inzwischen
anderweitig modifizierte DLL wird nicht automatisch ueberschrieben.
Steam-Dateipruefungen oder Spielupdates koennen den Patch entfernen.

FEHLERSUCHE
- Die URL haengt weiter bei Please Wait:
  Pruefen, ob der Server laeuft und ob http://127.0.0.1:8765/ erreichbar ist.
  Im Serverfenster nach Fehlermeldungen schauen.
- Die URL zeigt weiterhin auf aldagames.com:
  Vermutlich wurde eine andere DLL-Kopie ausgewaehlt oder Steam hat sie ersetzt.
- Meldung: Klartext-data fehlt:
  Beim Server kommt die alte verschluesselte Anfrage an. Patch-Installation pruefen.
- Auf der Webseite fehlen die vier Optionen:
  Spielrunde starten. Die Optionen werden erst bei newFloor uebermittelt.
- Keine Item-Vergabe:
  Vor der Auswertung wenigstens einmal im Browser abstimmen; der Installer muss
  fuer den Ein-Stimmen-Test mit minimum-votes 1 gelaufen sein.
- Python-Fenster schliesst sich oder Python fehlt:
  Die BAT-Dateien verwenden zunaechst py -3, sonst python. Eine lokale Python-
  Installation mit Launcher verwenden; die benoetigten Skripte liegen im Paket.
- Bei Problemen bitte kr_voting.log und den genauen sichtbaren Ablauf schicken.
  Fuer ein Unity-Spielproblem ist ausserdem output_log.txt aus dem Spiel relevant,
  falls diese Datei erzeugt wird. Vor dem Teilen private Angaben pruefen.

DATEIEN
patch_game.py          Versionspruefung, Patch, Original-Sicherung, Ruecksicherung
patch_manifest.json    Exakte gepruefte Aenderungsbereiche und SHA-256-Pruefsummen
server.py             HTTP-Spielprotokoll, Abstimmungs-API, SQLite-Speicherung
web/                  Browser-Oberflaeche
items.json            Optionale Anzeigenamen/Beschreibungen fuer Item-Kennungen
tests/                HTTP-Integrationstests und Schutz vor falscher DLL-Version
TECHNIK.md            Analysierter Ablauf, Umfang und Grenzen der Verifikation
kr_voting.sqlite3     Wird beim Start erstellt; enthaelt Spielrunden und Stimmen
kr_voting.log         Wird beim Start erstellt; enthaelt Diagnoseereignisse

OPTIONALE ITEM-ANZEIGENAMEN
items.json kann spaeter zum Beispiel so ergaenzt werden:
  {"TATSAECHLICHE_ITEM_KENNUNG": {"name": "Anzeigename", "description": "Beschreibung"}}
Dabei die Kennung exakt von der Abstimmungsseite uebernehmen; anschliessend
Server neu starten. Das leere mitgelieferte JSON ist bereits verwendbar.

PRUEFSTAND
Zwoelf HTTP-/Installer-Tests sowie der DLL-Aenderungsumfang sind geprueft.
Dein Log bestaetigt den Verbindungsaufbau und die vier Kandidaten im echten Spiel.
Die korrigierte Item-Auswertung aus Version 0.1.1 muss dort noch bestaetigt werden.
