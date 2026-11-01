# Killing Room: lokale Wiederherstellung der Zuschauer-Abstimmung

Stand: 1. November 2026, Version 0.1.1. Arbeitsgrundlage sind die vom Nutzer
hochgeladene `Assembly-CSharp.dll` aus `Assembly-CSharp.rar` und sein Laufzeitlog
der Version 0.1 vom selben Tag.

## Korrektur der Level-Zuordnung in 0.1.1

Das Nutzerlog zeigte eine geöffnete Abstimmung für Level 1 und anschließend
eine Auswertung für Level 2 mit null Stimmen. In der DLL bestätigt
`CPlayerInfoPersistent.CalculateFinishLevel`, dass `actualFloor` bereits vor
der Auswertung erhöht wird; beim konfigurierten letzten Level wird es gekappt.

Version 0.1 verlangte irrtümlich dieselbe `floor`-Zahl bei `newFloor` und
`endFloor`. Version 0.1.1 ordnet die Auswertung der aktuellen Kandidatenrunde zu,
sofern die angefragte Zahl unverändert oder um eins erhöht ist. Ein Fingerprint
aus `cr`, `sr` und angefragter Levelnummer bindet wiederholte Anfragen dauerhaft
an ihre Runde. Dadurch schließt ein verspäteter Retry keine neuere Abstimmung.
Die neue SQLite-Tabelle `end_floor_replies` wird ohne Änderung vorhandener
Runden oder Stimmen angelegt. Die DLL-Patchbytes sind gegenüber 0.1 unverändert.

Der gemeldete Ablauf wurde vor der Korrektur als fehlgeschlagener Test
reproduziert und besteht mit der Korrektur. Speichern oder Ändern einer Stimme
wird jetzt zusätzlich protokolliert. `/favicon.ico` antwortet mit 204.

## Eingabedatei

- Dateigröße: 1.262.592 Bytes.
- SHA-256: `d98154467f1a7c64b37da72f32464e9e45a8ffa2aeb1bf5a897059e221942cf9`.
- CLI-Metadatenversion: `v2.0.50727`; keine Strong-Name-Signatur.
- Die früher festgestellte Unity-Version 5.3.4f1 stammt aus der früheren
  Untersuchung von `globalgamemanagers`, nicht aus einer neuen Engine-Prüfung.

## Im Code bestätigter Ablauf

1. `CConnectToServer.DoHit` ruft `HTTP.CreateGetStartupMessageRequest` auf.
   Dessen POST an `startGame` enthält `data` mit `cr`, `sr=0`, `uid`, `floor`.
2. Bei einer Antwort mit `cr != 0` folgt `CreateGetStarDataRequest` am selben
   Endpunkt mit `sid`, verändertem `sr`, neuem `cr`, Gerätekennung und Profil.
   Der Spielername ist UTF-8/Base64; `steamName` wird separat angehängt.
3. `GetStartData` erwartet unter der XML-Wurzel `cr`, `error`, `sr`, `gid`, `url`.
4. `newFloor` übermittelt `cr`, `uid`, `gid`, `sr`, `floor`, `items`.
   Die Item-Kennungen sind kommasepariert. Beim initialen Aufbau und beim
   Generieren der nächsten Kandidaten sind die ersten zwei positiv, die
   folgenden negativ. Auf dem Draht ist `floor = actualFloor - 1`.
5. `endFloor` verlangt das Ergebnis. Der Client liest
   `votesCount` und `<votes><item name="KENNUNG">ANZAHL</item></votes>`.
   Es werden alle Kandidaten geliefert, auch solche mit null Stimmen.
6. `CUIVotingResults.LoadVotes` verlangt im Original mindestens drei Stimmen.
   Bei ausreichender Teilnahme gewinnt das Item mit dem höchsten Stimmenwert.
   Gleichstände behandelt die unveränderte Spielmethode in Kandidatenreihenfolge.

Weitere bestätigte Endpunkte: `endGame`, `saveBossStat`, `getBossStat`.
Der Ersatzserver führt eigene lokale Boss-Zähler und ersetzt keine historischen
Statistiken des ehemaligen Servers.

## Warum die alten KLC-Werte für diesen Patch entfallen

`HTTP.GetCrypted(string)` und `HTTP.GetDecrypted(string)` sind getrennte,
statische Wrapper ausschließlich für das untersuchte HTTP-Protokoll.
Der Patch ersetzt deren Methodenrumpf durch `ldarg.0; ret`. Dadurch werden
Spielanfragen als Klartext im Formularfeld `data` und Antworten als Klartext-XML
über die lokale Verbindung übertragen. Der übrige Request-/Parser-/Gameplay-Code
bleibt bestehen.

`CKillingCrypt.GetCrypted/GetDecrypted`, `CKeyManager`, `CCrypt` sowie die
Methoden für Spielstände, Einstellungen und Eingaben bleiben bytegleich.
Die Originalwerte `KLC.sr1/sr2/sr3` wurden nicht extrahiert. Die Verschlüsselung
des alten Dienstes wird nicht nachgebildet; der Patch verwendet gezielt einen
eigenen lokalen Transport mit dem beobachteten Nutzdatenformat.

## Genaue Änderungen

- Sechs ausschließlich von `CConfigUrls` geladene URL-Konstanten werden von
  `https://aldagames.com` nach `http://127.0.0.1:8765` umgestellt.
  Beide Präfixe haben dieselbe Länge; alle String-Heap-Offsets bleiben erhalten.
- Die im Spiel verwendete URL-Obfuskation `AldaHash` wird korrekt umgekehrt und
  neu angewendet. Das Terminalflag jeder betroffenen `#US`-Zeichenfolge wird
  entsprechend ECMA-335 gesetzt; die Blob-Längen bleiben identisch.
- Zwei Netzwerkmethoden werden durch die Identitätsabbildung ersetzt. Ihre
  Fat-Header behalten die gültigen lokalen Signaturen und aktualisieren `CodeSize`.
- Nur für den Ein-Stimmen-Test wird in `LoadVotes` ein `ldc.i4.3` zu `ldc.i4.1`.
  `--minimum-votes 3` lässt diese Originalregel unverändert.
- Dateigröße, Metadaten-Tabellen, Methodensignaturen und RVA-Adressen bleiben
  unverändert. Der Installer akzeptiert ausschließlich die bekannte SHA-256.

Die `cr`-Antwort wird entsprechend der originalen IL-Arithmetik berechnet:

```text
cr_antwort = ((floor(cr / 31) + 1) * (cr mod 17 + 3) * 7) + 71
sr_anfrage = ((floor(sr / 53) + 3) * (sr mod 29 + 1) * 11) + 79
```

`ValidateConnection` liefert in dieser Original-DLL ohnehin konstant `true`.
Der Ersatzserver bleibt bei den im Client beobachteten Feldnamen und erzeugt
positive ganzzahlige Challenges, um kulturabhängige Dezimaltrennzeichen zu umgehen.

## Ersatzserver

Python-Standardbibliothek, standardmäßig ausschließlich Loopback `127.0.0.1:8765`.
Unterstützt URL-Formulare und Multipart-Formulare aus Unity `WWWForm`.
Spiel-ID und öffentlicher Zuschauer-Token sind voneinander getrennt.
Stimmen werden in SQLite gespeichert; pro Browser-Cookie und Abstimmungsrunde
gibt es eine änderbare Stimme. Cookies können zurückgesetzt werden: Dies ist
keine starke Identitätsprüfung für einen öffentlichen Dienst.

Wiederholte `startGame`-Schritte mit derselben `sid` erzeugen keine zweite Runde.
Wiederholte `newFloor`-Anfragen mit denselben Optionen erhalten die Stimmen.
`endFloor` schließt die Runde und liefert bei Wiederholungen dieselben Stimmen.
Neue Level beziehungsweise neue Kandidatensätze erhalten eine eigene Abstimmung.

## Verifikation und verbleibender Test

- Zwölf automatisierte HTTP-/Installer-Tests: Handshake,
  Multipart, Base64-Pluszeichen, Abstimmen/Ändern, getrennte Browser, Wiederholungen,
  Levelwechsel, geschlossene Runden, Persistenz, XML-Escaping, Boss-Deduplizierung,
  fremde Origin und unbekannte DLL. Zusätzlich: gemeldeter Levelversatz,
  verspäteter Retry nach Levelwechsel, gekappter letzter Level, Migration einer
  bestehenden 0.1-Datenbank und Schutz der aktuellen Runde bei falscher Levelnummer.
- Beide Patchvarianten werden erneut mit `dnfile` und `dncil` geparst.
  Alle übrigen Methodenrümpfe werden byteweise mit dem Original verglichen.
- Die Challenge-Berechnung wird für 28 Fälle durch Auswertung der originalen
  IL-Instruktionen gegen die Python-Implementierung geprüft.
- Installation, Wechsel zwischen Ein-/Drei-Stimmen-Regel und Rücksicherung werden
  mit einer Kopie der hochgeladenen Originaldatei geprüft. Fremde Änderungen
  werden beim Restore nicht überschrieben.
- Der Nutzer hat den Verbindungsaufbau und die Übermittlung der vier Kandidaten
  aus dem echten Spiel mit Version 0.1 protokolliert. Die korrigierte Auswertung
  mit 0.1.1 sowie die tatsächliche Item-Vergabe sind noch nicht im Spiel bestätigt.

Als Nächstes ist auf dem Spiel-PC zu prüfen: neue Zuschauer-URL, vier Kandidaten,
mindestens eine Stimme, Levelauswertung und tatsächliche Item-Vergabe.
Danach folgen die Anbindung externer Zuschauer sowie Namen und Bilder aus
zusätzlichen Spiel-Assets. Diese Aufgaben sind in Version 0.1.1 noch offen.

## Formatquellen

- [ECMA-335, 6. Ausgabe, Partition II](https://www.ecma-international.org/wp-content/uploads/ECMA-335_6th_edition_june_2012.pdf),
  insbesondere II.24.2.4 (`#US`-Strings) und II.25.4 (Methodenrümpfe).
- [Microsoft: BlobWriter.WriteUserString](https://source.dot.net/System.Reflection.Metadata/System/Reflection/Metadata/BlobWriter.cs.html).
- [Microsoft: IL-Methodenheader](https://learn.microsoft.com/en-us/archive/msdn-magazine/2003/september/write-msil-code-on-the-fly-with-the-net-framework-profiling-api).

Die Spielprotokoll-Befunde stammen aus der statischen Analyse der bereitgestellten
Datei; Serverantworten sind eine Implementierung anhand der Client-Erwartungen.
