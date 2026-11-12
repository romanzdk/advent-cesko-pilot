import { draftURL, ISSUES, ISSUES_API, issueViews, REGIONS, CATEGORIES } from './feedback-helpers.js';

const byId = id => document.getElementById(id);
const form = byId('feedback-form');
for (const [id, values] of [['feedback-region', REGIONS.map(value => [value, value])], ['feedback-category', Object.entries(CATEGORIES)]]) {
  for (const [value, label] of values) {
    const option = document.createElement('option');
    option.value = value; option.textContent = label;
    byId(id).append(option);
  }
}
function clearDraft() {
  byId('feedback-draft').hidden = true;
  byId('feedback-draft').removeAttribute('href');
  byId('feedback-message').textContent = '';
}
function syncMode() {
  const full = byId('feedback-mode').value === 'full';
  for (const section of form.querySelectorAll('[data-full]')) {
    section.hidden = !full;
    for (const control of section.querySelectorAll('input, select, textarea')) control.disabled = !full;
  }
  for (const id of ['feedback-title', 'feedback-town', 'feedback-source']) byId(id).required = full;
  const unknown = byId('feedback-date-unknown').checked;
  for (const id of ['feedback-date', 'feedback-end-date', 'feedback-start-time', 'feedback-end-time']) byId(id).disabled = !full || unknown;
  byId('feedback-date').required = full && !unknown;
  byId('feedback-town-label').firstChild.textContent = `Obec (${full ? 'povinné' : 'nepovinné'}, max. 100 znaků)`;
  byId('feedback-source-label').firstChild.textContent = `Veřejný zdroj akce (${full ? 'povinné' : 'nepovinné'}, max. 800 znaků)`;
  clearDraft();
}
byId('feedback-mode').addEventListener('change', syncMode);
byId('feedback-date-unknown').addEventListener('change', syncMode);
form.addEventListener('input', clearDraft);
syncMode();
form.addEventListener('submit', event => {
  event.preventDefault();
  const message = byId('feedback-message'), link = byId('feedback-draft');
  link.hidden = true;
  try {
    const data = Object.fromEntries(new FormData(form));
    data.consent = byId('feedback-consent').checked;
    data.dateUnknown = !byId('feedback-date-unknown').disabled && byId('feedback-date-unknown').checked;
    const url = draftURL(data);
    link.href = url;
    link.hidden = false;
    message.textContent = 'Návrh je připraven; nejde o publikaci ani přidání do mapy. Přihlášení a odeslání dokončíte na GitHubu. Pokud se nová karta neotevřela, použijte odkaz níže.';
    try { window.open(url, '_blank', 'noopener,noreferrer'); } catch { /* The prepared link remains usable when popups fail. */ }
  } catch (error) { message.textContent = error.message; }
});
form.hidden = false;
byId('feedback-search').addEventListener('input', event => {
  byId('feedback-search-link').href = `${ISSUES}?${new URLSearchParams({ q: `is:issue ${event.target.value.trim()}` })}`;
});
let requested = false;
byId('feedback').addEventListener('toggle', async () => {
  if (!byId('feedback').open || requested) return;
  requested = true;
  const status = byId('feedback-list-status');
  status.textContent = 'Načítáme poslední hlášení…';
  try {
    const response = await fetch(ISSUES_API, { credentials: 'omit', signal: AbortSignal.timeout(5000) });
    if (!response.ok) throw new Error('Issue list unavailable');
    const issues = issueViews(await response.json());
    for (const issue of issues) {
      const row = document.createElement('li'), link = document.createElement('a');
      link.href = issue.url;
      link.textContent = `${issue.state === 'open' ? 'Otevřeno' : 'Uzavřeno'} · ${issue.title}`;
      row.append(link);
      byId('feedback-issues').append(row);
    }
    status.textContent = issues.length ? 'Nedávno aktualizovaná hlášení:' : 'V tomto výběru nejsou žádná hlášení. Ověřte také celý seznam na GitHubu.';
  } catch {
    status.textContent = 'Seznam se nepodařilo načíst. Prohlédněte tipy přímo na GitHubu; formulář můžete použít i tak.';
  }
});
