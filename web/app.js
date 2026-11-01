'use strict';
const tokenMatch = location.pathname.match(/^\/v\/([A-Za-z0-9_-]{20,64})$/);
const statusLabel = document.getElementById('status');
const totalLabel = document.getElementById('total');
const message = document.getElementById('message');
const optionHolder = document.getElementById('options');
const subtitle = document.getElementById('subtitle');
let submitting = false;
let latest = null;
let pollTimer = null;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function render(data) {
  const focusedItem = document.activeElement?.dataset?.item;
  latest = data;
  if(data.ended && pollTimer)clearInterval(pollTimer);
  subtitle.textContent = 'Du stimmst für ' + data.player + '. Belohnung oder Bestrafung: Du entscheidest mit.';
  totalLabel.textContent = data.votesCount + ' / ' + (data.minimum_votes || 1) + ' Mindeststimmen';
  document.getElementById('hint').textContent = 'Benötigt: ' + (data.minimum_votes || 1) + ' Stimmen. Eine änderbare Stimme pro Browser; in Discord eine pro Discord-Konto.';
  statusLabel.textContent = data.ended ? 'Spielrunde beendet' : data.floor === null ? 'Warten auf den ersten Level' : 'Level ' + data.floor + ' · ' + (data.active ? 'Abstimmung läuft' : 'Abstimmung beendet');
  message.textContent = data.ended ? 'Diese Spielrunde ist beendet. Für die nächste Runde erhältst du einen neuen Link.' : data.items.length === 0 ? 'Sobald das Spiel die vier Item-Kandidaten übermittelt, erscheinen sie hier automatisch.' : data.active ? '' : 'Die Auswertung wurde vom Spiel angefordert. Sobald der nächste Level beginnt, erscheinen die neuen Optionen.';
  optionHolder.replaceChildren();
  for (const item of data.items) {
    const selected = data.choice === item.id;
    const card = element('button', 'option ' + (item.kind === 'bad' ? 'bad' : 'good') + (selected ? ' selected' : ''));
    card.type = 'button';
    card.dataset.item = item.id;
    card.disabled = !data.active || submitting;
    card.setAttribute('aria-pressed', String(selected));
    const meta = element('div', 'option-meta');
    meta.append(element('span', '', item.kind === 'good' ? '＋ BELOHNUNG' : '− BESTRAFUNG'));
    if (selected) meta.append(element('span', 'selection', 'DEINE STIMME'));
    card.append(meta, element('h2', '', item.label));
    if (item.description) card.append(element('p', 'description', item.description));
    const percent = data.votesCount ? Math.round(item.votes / data.votesCount * 100) : 0;
    const result = element('div', 'result');
    result.append(element('span', '', item.votes + (item.votes === 1 ? ' Stimme' : ' Stimmen')), element('span', '', percent + ' %'));
    const meter = element('div', 'meter');
    const fill = element('div', 'fill');
    fill.style.width = percent + '%';
    meter.append(fill);
    card.append(result, meter);
    card.addEventListener('click', () => castVote(data.round_id, item.id));
    optionHolder.append(card);
  }
  if (focusedItem) [...optionHolder.children].find(card => card.dataset.item === focusedItem)?.focus();
}

async function fetchState() {
  try {
    const response = await fetch('/api/v/' + tokenMatch[1], {cache: 'no-store'});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Abstimmung konnte nicht geladen werden.');
    if (!submitting) render(data);
  } catch (error) {
    statusLabel.textContent = 'Verbindung unterbrochen';
    message.textContent = error.message + ' Die Verbindung wird automatisch erneut versucht.';
  }
}

async function castVote(roundId, item) {
  if (submitting) return;
  submitting = true;
  if (latest) render(latest);
  try {
    const response = await fetch('/api/v/' + tokenMatch[1], {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({round_id: roundId, item})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Stimme konnte nicht gespeichert werden.');
    submitting = false;
    render(data);
  } catch (error) {
    submitting = false;
    if (latest) render(latest);
    message.textContent = error.message;
  }
}

if (tokenMatch) {
  fetchState();
  pollTimer=setInterval(() => { if (!submitting && !document.hidden) fetchState(); }, 2500);
  document.addEventListener('visibilitychange', () => { if (!document.hidden && !latest?.ended) fetchState(); });
} else {
  statusLabel.textContent = 'Voting-Server ist erreichbar';
  totalLabel.textContent = '';
  subtitle.textContent = 'Verbinde deinen Spiel-PC mit diesem Server und teile anschließend deinen Zuschauerlink.';
  message.textContent = 'Trage ' + location.origin + ' als client.server_url in deiner settings.json ein und starte EINSTELLUNGEN_ANWENDEN.bat. Dein API-Schlüssel wird beim ersten Verbinden automatisch erzeugt und registriert. Starte danach 3_SPIEL_PC_VERBINDEN.bat und Killing Room.';
  document.getElementById('hint').textContent = 'Zuschauer öffnen den Link, den das Spiel erzeugt. Sie benötigen keinen API-Schlüssel.';
  fetch('/api/config', {cache:'no-store'}).then(response => response.json()).then(config => {
    if (!config.registration_enabled) message.textContent = 'Starte Killing Room mit dem lokalen Patch und erzeuge im Startmenü die Zuschauer-URL. Öffne genau diesen Link zum Abstimmen. Der Server nimmt derzeit keine neuen Spiel-PCs automatisch auf.';
  }).catch(() => { statusLabel.textContent = 'Verbindung unterbrochen'; });
}
