import { draftURL, proposalPayload, feedbackRequest, ISSUES, ISSUES_API, issueViews, REGIONS, CATEGORIES } from './feedback-helpers.js';
import { eventPermalink } from './helpers.js';

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
const uuid = value => typeof value === 'string' && /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(value);
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const newState = () => ({ busy: false, locked: false, message: '', result: '', draft: '', fields: [] });
// Each report owns every async continuation, token and delivery identity. No await
// writes to a shared DOM target; render only accepts the currently selected state.
function sender(prefix, build, manual) {
  const target = byId(`${prefix}-form`), submit = target.querySelector('button[type=submit]');
  const fallback = byId(`${prefix}-fallback`), direct = byId(`${prefix}-direct-draft`);
  const states = new Map();
  let selected = newState();
  function render(state) {
    if (state !== selected) return;
    byId(`${prefix}-message`).textContent = state.message;
    for (const key of ['result', 'draft']) {
      const link = byId(`${prefix}-${key}`);
      link.hidden = !state[key] || key === 'draft' && (state.locked || state.busy);
      if (state[key]) link.href = state[key]; else link.removeAttribute('href');
    }
    submit.disabled = state.busy;
    submit.formNoValidate = state.locked; // A GET status check never re-validates an edited proposal.
    submit.textContent = state.locked ? 'Ověřit stav znovu' : 'Odeslat bez účtu';
    fallback.disabled = state.busy || state.locked;
    if (direct) direct.hidden = state.busy || state.locked;
  }
  async function challenge(state, refresh = false) {
    if (refresh) { state.token = ''; state.preparing = null; }
    if (state.token) return state.token;
    if (!state.preparing) {
      const pending = feedbackRequest('/api/challenge').then(async data => {
        if (typeof data.challenge !== 'string' || !data.challenge) throw new Error('Ověření není dostupné.');
        await sleep(2100);
        if (state.preparing === pending) state.token = data.challenge;
        return data.challenge;
      }).finally(() => { if (state.preparing === pending) state.preparing = null; });
      state.preparing = pending;
    }
    return state.preparing;
  }
  function display(state, data) {
    if (!uuid(data.requestId) || !['pending', 'uncertain', 'submitted', 'failed'].includes(data.status)) throw new Error('Neplatná odpověď služby.');
    state.acceptedId = data.requestId;
    state.status = data.status;
    state.result = '';
    if (data.status === 'submitted') {
      if (!/^https:\/\/github\.com\/romanzdk\/advent-cesko-pilot\/issues\/[1-9]\d*$/.test(data.issueURL || '')) throw new Error('Zveřejnění nelze potvrdit.');
      state.result = data.issueURL;
      state.message = 'Zveřejněno na GitHubu. Zařazení do mapy není automatické.';
    } else if (data.status === 'pending') state.message = 'Přijato do fronty. Zveřejnění na GitHubu zatím není potvrzeno.';
    else if (data.status === 'uncertain') state.message = 'Zveřejnění není jisté. Nevytvářejte další hlášení; ověřte stav znovu.';
    else state.message = 'Zveřejnění se nezdařilo. Návrh zůstává vyplněný; ověřte stav znovu, nevytvářejte další kopii.';
    render(state);
  }
  fallback.addEventListener('click', () => {
    const state = selected;
    if (state.busy || state.locked || !target.reportValidity()) return;
    try {
      const proposal = build(Object.fromEntries(new FormData(target)));
      state.draft = manual(proposal);
      state.message = 'Potřebujete účet GitHub. Návrh zkontrolujte; přihlášení a odeslání dokončíte na GitHubu. Příprava odkazu nic neodesílá; pokud se karta neotevře, použijte odkaz níže.';
      render(state);
      try { window.open(state.draft, '_blank', 'noopener,noreferrer'); } catch { /* Link remains usable. */ }
    } catch (error) { state.message = error.message; render(state); }
  });
  target.addEventListener('input', () => { selected.draft = ''; render(selected); });
  target.addEventListener('submit', async event => {
    event.preventDefault();
    const state = selected;
    if (state.busy || !state.locked && !target.reportValidity()) return;
    state.busy = true; state.draft = ''; render(state);
    let posting = false;
    try {
      let data;
      if (state.locked) {
        data = await feedbackRequest(`/api/submissions/${state.acceptedId || state.payload.requestId}`);
      } else {
        const proposal = build(Object.fromEntries(new FormData(target))), key = JSON.stringify(proposal);
        if (state.key !== key) { state.key = key; state.payload = { ...proposal, requestId: crypto.randomUUID() }; }
        state.message = 'Připravujeme bezpečné odeslání…'; render(state);
        state.payload.challenge = await challenge(state);
        // The proposal is captured before awaiting; a switch cannot change its event ID.
        state.locked = true; posting = true; render(state);
        data = await feedbackRequest('/api/submissions', state.payload);
        posting = false; // Poll errors cannot turn an accepted POST into a preaccept rejection.
        state.token = '';
      }
      display(state, data);
      const deadline = Date.now() + 20000;
      for (let attempt = 0; attempt < 20 && ['pending', 'uncertain'].includes(state.status) && Date.now() < deadline; attempt++) {
        await sleep(Math.min(1000, deadline - Date.now()));
        if (Date.now() >= deadline) break;
        data = await feedbackRequest(`/api/submissions/${state.acceptedId}`, undefined, Math.min(8000, deadline - Date.now()));
        display(state, data);
      }
      if (['pending', 'uncertain'].includes(state.status)) state.message += ' Ověřte stav znovu; neposílejte další kopii.';
    } catch (error) {
      // Only these definitive preaccept rejections release the duplicate lock.
      const rejected = posting && ['challenge', 'validation', 'rate_limit', 'too_large', 'content_type', 'origin'].includes(error.code) && [400, 403, 413, 415, 429].includes(error.http);
      if (rejected) state.locked = false;
      if (rejected && error.code === 'challenge') {
        try {
          const token = await challenge(state, true);
          state.payload.challenge = token;
          state.message = 'Ověření obnoveno. Zkuste návrh odeslat znovu.';
        } catch { state.message = 'Ověření nelze obnovit. Zkuste znovu později.'; }
      } else state.message = state.locked ? 'Odeslání či zveřejnění nelze potvrdit. Nevytvářejte další hlášení; ověřte stav znovu. Obsah zůstává vyplněný.' : (error.message || 'Odesílání není dostupné. Zkuste znovu nebo použijte ruční návrh na GitHubu.');
    } finally { state.busy = false; render(state); }
  });
  return {
    prepare() { const state = selected; challenge(state).catch(() => {}); },
    select(id) {
      selected.fields = Array.from(target.elements).filter(n => n.matches('input,select,textarea')).map(n => ({ name: n.id || n.name, value: n.value, checked: n.checked }));
      if (!states.has(id)) states.set(id, newState());
      selected = states.get(id); target.reset();
      for (const field of selected.fields) {
        const input = target.elements.namedItem(field.name);
        if (input) { input.value = field.value; input.checked = field.checked; }
      }
      render(selected);
    }
  };
}
let catalogue = [], reportedEvent, reportTrigger;
const dialog = byId('report-dialog');
const report = sender('report', fields => proposalPayload({ ...fields, mode: 'error', eventId: reportedEvent.id, consent: byId('report-consent').checked }), proposal => {
  const body = `Neověřené veřejné hlášení k ruční kontrole.\n\n${Object.entries(proposal).filter(([key]) => !['consent', 'website'].includes(key)).map(([key, value]) => `${key}: ${String(value).replaceAll('@', '@\u200b').replaceAll('`', 'ˋ')}`).join('\n')}`;
  const url = `${ISSUES}/new?${new URLSearchParams({ title: '[Chyba] Oprava akce', body })}`;
  if (url.length > 7000) throw new Error('Návrh je příliš dlouhý pro ruční odkaz. Zkraťte jej.');
  return url;
});
byId('report-close').addEventListener('click', () => dialog.close());
dialog.addEventListener('close', () => {
  const trigger = reportTrigger?.isConnected ? reportTrigger : Array.from(document.querySelectorAll('.event-card')).find(n => n.dataset.id === reportedEvent?.id)?.querySelector('.report-button');
  trigger?.focus({ preventScroll: true });
});
const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
function showMatches() {
  const town = normalize(byId('feedback-town').value), title = normalize(byId('feedback-title').value);
  const matches = catalogue.filter(event => town && normalize(event.town) === town || title.length >= 4 && normalize(event.title).includes(title)).slice(0, 5);
  const box = byId('feedback-matches'); box.replaceChildren(); box.hidden = !matches.length;
  if (!matches.length) return;
  const heading = document.createElement('p'); heading.textContent = 'Podobné akce už jsou v přehledu. Nejde o úplnou kontrolu duplicit:'; box.append(heading);
  for (const event of matches) {
    const row = document.createElement('p'), link = document.createElement('a');
    link.href = eventPermalink(event.id, new URL('./', import.meta.url));
    link.textContent = `${event.title} · ${event.town} · ${event.date}`; row.append(link); box.append(row);
  }
}
for (const id of ['feedback-town', 'feedback-title']) byId(id).addEventListener('input', showMatches);
document.addEventListener('advent:catalog', ({ detail }) => { catalogue = detail; showMatches(); });
document.addEventListener('advent:report', ({ detail }) => {
  const event = catalogue.find(item => item.id === detail.id);
  if (!event) return;
  if (reportedEvent?.id !== event.id) report.select(event.id);
  reportedEvent = event; reportTrigger = detail.trigger;
  byId('report-context').textContent = `${event.title} · ${event.town} · ${event.venue || ''} · ${event.date}`;
  byId('report-search').href = `${ISSUES}?${new URLSearchParams({ q: `is:issue "${event.id}"` })}`;
  dialog.showModal(); byId('report-kind').focus();
  // Readiness never writes a status: a late rejection for A cannot overwrite B.
  report.prepare();
});
document.dispatchEvent(new CustomEvent('advent:catalog-request'));
document.documentElement.dataset.feedbackReady = 'true';
document.dispatchEvent(new CustomEvent('advent:feedback-ready'));
const feedback = sender('feedback', fields => proposalPayload({ ...fields, consent: byId('feedback-consent').checked, dateUnknown: byId('feedback-date-unknown').checked }), proposal => draftURL({ ...proposal, mode: proposal.mode === 'event' ? 'full' : 'quick' }));
byId('feedback').addEventListener('toggle', () => { if (byId('feedback').open) feedback.prepare(); });
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
      row.append(link); byId('feedback-issues').append(row);
    }
    status.textContent = issues.length ? 'Nedávno aktualizovaná hlášení:' : 'V tomto výběru nejsou žádná hlášení. Ověřte také celý seznam na GitHubu.';
  } catch { status.textContent = 'Seznam se nepodařilo načíst. Prohlédněte tipy přímo na GitHubu; formulář můžete použít i tak.'; }
});
