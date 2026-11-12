import { draftURL, ISSUES, ISSUES_API, issueViews } from './feedback-helpers.js';

const byId = id => document.getElementById(id);
const form = byId('feedback-form');
form.addEventListener('submit', event => {
  event.preventDefault();
  const message = byId('feedback-message'), link = byId('feedback-draft');
  link.hidden = true;
  try {
    const url = draftURL({ town: byId('feedback-town').value, sourceURL: byId('feedback-source').value, description: byId('feedback-description').value, consent: byId('feedback-consent').checked });
    link.href = url;
    link.hidden = false;
    window.open(url, '_blank', 'noopener,noreferrer');
    message.textContent = 'Odeslání dokončíte na GitHubu. Pokud se nová karta neotevřela, použijte odkaz na připravený návrh níže.';
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
