# Community Content 0.1.0 — Alpha

[English instructions](README.en.md)

Zusätzliches Inhaltspaket für den untersuchten Killing-Room-Build mit Unity
5.3.4f1. Es wird über BepInEx 5.4.23.6 geladen. Die vorhandene Spiel-DLL und der
Voting-Patch werden bei der Installation nicht verändert.

**Status:** Gegen die tatsächlich bereitgestellten Spieldateien kompiliert.
Die Regel- und Installer-Tests sowie der statische Abgleich der Spielmethoden
sind bestanden. Ein Start im Windows-Spiel wurde hier noch nicht geprüft.
Die erste Verwendung sollte deshalb eine neue Test-Spielrunde sein.

## Installation für Spieler

1. Das fertige **Community-Content-Alpha-Paket** vollständig entpacken. Ein reiner
   GitHub-Quellcode-Download enthält die kompilierte Plugin-DLL nicht.
2. Killing Room vollständig beenden. Python 3.10 oder neuer wird für den
   Installer benötigt; fürs Spielen selbst genügt anschließend der Spielstart.
3. `INSTALLIEREN.bat` doppelklicken und die `KillingRoom.exe` im Spielordner wählen.
   Der Installer erkennt 32-/64-Bit automatisch und lädt die dazu passende,
   festgelegte BepInEx-Version vom offiziellen Release herunter. Die Prüfsummen
   werden vor dem Schreiben kontrolliert. Internet ist für diesen Schritt nötig.
4. Spiel starten. Mit **F6 im Hauptmenü** die Challenge der nächsten neuen Runde
   wählen. **F8** schaltet die Mod-Anzeige einschließlich Elite-Namen ein/aus.
5. Für Online-Voting weiterhin den bisherigen Server beziehungsweise
   `3_SPIEL_PC_VERBINDEN.bat` verwenden. Für dieses Inhaltspaket ist kein weiterer
   lokaler Server nötig.

Ein vorhandener anderer Loader oder eine abweichende BepInEx-Version wird nicht
überschrieben. In diesem Fall die Installation mit der vorhandenen Mod-Umgebung
abgleichen und die Plugin-DLL bei passender Runtime manuell unter
`BepInEx/plugins/KillingRoomCommunity/` ablegen.

## Vier Challenges

| Auswahl mit F6 | Regeln |
| --- | --- |
| `Off` | Keine zusätzliche Challenge. Neue Items und Gegnervarianten bleiben aktiv. |
| `GlassCannon` | 35 % mehr direkter Spielerschaden; dafür 50 % mehr eingehender Schaden. |
| `ArmsRoulette` | Nach einem abgeschlossenen Kampfraum wird eine andere bereits besessene Waffe gewählt, einschließlich Nahkampf. Bei nur einer Waffe bleibt sie erhalten. |
| `Showtime` | Standardziel: Kampfräume in höchstens 45 Sekunden abschließen. Danach für den laufenden Raum 25 % mehr eingehender Schaden. Schnelle Abschlüsse geben je 2 % zusätzlichen direkten Schaden, höchstens 20 % pro Runde. Boss- und Rätselräume werden nicht auf Zeit gesetzt. |
| `ChaosBroadcast` | Pro Etage ein für diese Runde fest ausgewürfelter Modifikator: Turbo (Spieler +12 %, normale Gegner +15 % Tempo), Iron Broadcast (Spieler −15 % eingehender Schaden, normale Gegner +25 % Leben) oder Glass Air (+20 % direkter Schaden, +15 % eingehender Schaden). |

Die Auswahl wird beim ersten Kampfraum für die Runde festgeschrieben. Gespeicherte
Mod-Runden behalten ihre Challenge beim Fortsetzen.

## Sechs Items

Die Items verwenden eigene Kennungen, Namen und Effekte sowie vorhandene
Spiel-Icons. Sie können in den normalen Loot- und Voting-Auswahlen erscheinen;
die Zufallsauswahl garantiert nicht, dass jedes Item in jeder Runde auftaucht.

| Item | Effekt |
| --- | --- |
| Adrenaline Battery | Nach einem abgeschlossenen Kampfraum 15 % Bewegungstempo für 8 Sekunden. |
| Echo Magazine | Jeder sechste geeignete Standard-Schuss/Schrotstoß löst einen zusätzlichen kostenlosen Schuss/Schrotstoß aus. Nahkampf und spezielle Projektilimplementierungen sind ausgenommen. |
| Emergency Relay | Nach einem überlebten Treffer bei höchstens 25 % Leben: 4 Sekunden lang 50 % weniger Schaden. 45 Sekunden Abklingzeit; keine Wiederbelebung. |
| Overheated Relay | 12 % mehr direkter Schaden, dafür 15 % mehr eingehender Schaden. Negatives Voting-Item mit Vorteil und Nachteil. |
| Lead Boots | −8 % der Geschwindigkeits-Statistikspanne, dafür +4 Verteidigungspunkte. |
| Static Coil | Nach jedem Kampfraum Verlust von 5 % der maximalen Rüstung; Leben wird nicht abgezogen. |

Für lesbare Namen im Zuschauer-Browser können Betreiber die sechs Einträge aus
`content-metadata.json` in ihre bestehende `items.json` übernehmen und den Server
neu starten. Eigene Einträge behalten. Im Quellcode dieses Zweigs sind die
sechs Namen bereits in der Standarddatei enthalten. Der Voting-Transport selbst
bleibt kompatibel; Spieler ohne Inhaltspaket können denselben Server verwenden.

## Drei Gegnervarianten

Standardchance: 18 % pro geeignetem normalen Gegner.

| Variante | Unterschied |
| --- | --- |
| Sprinter | 35 % schneller, dafür 20 % weniger Leben. |
| Juggernaut | 80 % mehr Leben, 20 % Schadensreduktion, dafür 25 % langsamer. |
| Medic | 15 % mehr Leben; heilt alle 4 Sekunden nahe lebende normale Verbündete im selben Raum um 6 % ihres maximalen Lebens. Keine Wiederbelebung und keine Boss-Heilung. |

Das sind neue Verhaltens-/Wertevarianten vorhandener Modelle. Eigene neue
3D-Modelle sind nicht enthalten. Boss-, Schneemann- und spezialisierte KI-Typen
sind zunächst ausgenommen. Es werden keine zusätzlichen Gegner gespawnt und
keine Raumzähler ersetzt.

## Konfiguration

Nach dem ersten Start liegt die Datei
`BepInEx/config/m4unz1.killingroom.content.cfg` im Spielordner. Spiel zum Bearbeiten
beenden, anschließend neu starten.

- `NextRun`: `Off`, `GlassCannon`, `ArmsRoulette`, `Showtime`, `ChaosBroadcast`.
- `ShowtimeSeconds`: 10–300, Standard 45.
- `GenerateNewItems`: Neue Items in Loot/Voting aufnehmen. `false` unterbindet
  ihre neue Generierung; bereits gespeicherte Items bleiben registriert.
- `EnableVariants`: Neue Gegnerrollen einschalten.
- `VariantChance`: 0–0.5, Standard 0.18.
- `ShowHud`: Anzeige und Elite-Namen.
- `EnableItemGrantKey`: Nur für Tests. Bei `true` gibt **F7** die drei positiven
  Mod-Items. Standardmäßig ausgeschaltet.

## Spielstände und Deaktivierung

Beim ersten Plugin-Start wird eine vorhandene `Save.json` einmal als
`Save.json.krce-original.bak` daneben gesichert. Existiert zu diesem Zeitpunkt
kein Save, wird das vermerkt und später kein modifizierter Save als ursprünglicher
Spielstand ausgegeben.

Die Ergänzungsdatei `Save.json.krce-state` speichert Challenge, Zufallszustand,
Item-Fortschritt und verbleibende Effektzeiten. Sie wird an die Prüfsumme des
zugehörigen Spielstands gebunden. Der native Spielstand wird weiterhin vom Spiel
selbst geschrieben; die Verschlüsselung wird nicht verändert.

**Ein gespeicherter Lauf mit neuen Item-Kennungen benötigt das Plugin zum
Fortsetzen.** Vor dem Entfernen den Mod-Lauf abschließen/verwerfen oder die
ursprüngliche Sicherung wiederherstellen. Die Sicherung behalten.

Zum Deaktivieren bei beendetem Spiel nur
`BepInEx/plugins/KillingRoomCommunity/KillingRoomCommunity.Content.dll` aus dem
`plugins`-Verzeichnis herausnehmen, etwa nach `BepInEx/disabled/`. Andere Mods,
BepInEx und den funktionierenden Voting-Patch dabei behalten.

## Erster Praxistest

1. Neue Runde starten; Hauptmenü und F6/F8 prüfen.
2. Einen normalen Kampfraum mit `Showtime` betreten und abschließen.
3. Elite-Namen, Raumabschluss und Türen prüfen.
4. Optional die Testtaste aktivieren, F7 drücken und Item-Anzeige, Echo sowie
   Adrenaline Battery ausprobieren.
5. Eine Mod-Runde an einer regulären Speicherstelle speichern, Spiel neu starten
   und fortsetzen. Challenge und Items prüfen.
6. Online-Voting mit einem neuen Item testen. Bei Fehlern
   `BepInEx/LogOutput.log` und die konkrete Aktion melden.

## Entwicklung

`build.py` benötigt einen .NET-SDK-Pfad, .NET-3.5-Referenzassemblies sowie externe
Referenzen aus dem eigenen Spiel und BepInEx. Siehe `build.py --help`. Keine
originalen Spiel-DLLs oder dekompilierten Spielklassen veröffentlichen.

Regeltests: `dotnet run --project tests/RulesTests.csproj -c Release`.
Installer-Tests: `python -m unittest discover -s tests -p 'test_*.py' -v`.
Statischer API-Abgleich: `python tools/verify_game_api.py /pfad/Assembly-CSharp.dll`.

Referenzen: [BepInEx 5.4.23.6](https://github.com/BepInEx/BepInEx/releases/tag/v5.4.23.6),
[Plugin-Entwicklung](https://docs.bepinex.dev/v5.4.11/articles/dev_guide/plugin_tutorial/1_setup.html).
