export const ISSUES = 'https://github.com/romanzdk/advent-cesko-pilot/issues';
export const ISSUES_API = 'https://api.github.com/repos/romanzdk/advent-cesko-pilot/issues?state=all&sort=updated&direction=desc&per_page=10';
export function issueViews(data) {
  if (!Array.isArray(data)) throw new Error('Invalid issue response');
  return data.filter(i => i && !i.pull_request && Number.isSafeInteger(i.number) && i.number > 0 && typeof i.title === 'string' && ['open', 'closed'].includes(i.state) && i.html_url === `${ISSUES}/${i.number}`).slice(0, 10).map(i => ({ title: i.title, state: i.state, url: i.html_url }));
}
export function draftURL({ town = '', sourceURL = '', description = '', consent }) {
  town = town.trim(); sourceURL = sourceURL.trim(); description = description.trim();
  if (town.length > 100 || sourceURL.length > 800 || description.length > 1000) throw new Error('Text je příliš dlouhý. Limity: obec 100, odkaz 800, popis 1000 znaků.');
  if (!town && !sourceURL && !description) throw new Error('Vyplňte obec, odkaz nebo popis.');
  if (consent !== true) throw new Error('Potvrďte, že návrh bude veřejný.');
  if (sourceURL) {
    try {
      const u = new URL(sourceURL), h = u.hostname.toLowerCase().replace(/\.$/, '');
      const [a, b] = h.split('.').map(Number);
      const privateIP = /^\d+\.\d+\.\d+\.\d+$/.test(h) && (a === 0 || a === 10 || a === 127 || a >= 224 || (a === 100 && b >= 64 && b <= 127) || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168));
      if (!/^https?:$/.test(u.protocol) || u.username || u.password || !h.includes('.') || h.includes(':') || /(?:^|\.)(localhost|local|internal|test|invalid)$/.test(h) || privateIP) throw new Error();
    } catch { throw new Error('Použijte veřejný odkaz HTTP nebo HTTPS bez přihlašovacích údajů.'); }
  }
  const title = `[Tip] ${town || description.split('\n')[0] || new URL(sourceURL).hostname}`;
  if (title.length >= 120) throw new Error('Název je příliš dlouhý. Zkraťte první řádek popisu nebo doplňte obec.');
  const body = `### Obec\n${town}\n\n### Veřejný zdroj\n${sourceURL}\n\n### Podrobnosti\n${description}\n\nObdobí: 20. 11. – 24. 12. 2026. Návrh je veřejný, bez osobních údajů. Zařazení do mapy není automatické.\nPřed odesláním prosím zkontrolujte existující tipy.`;
  const url = `${ISSUES}/new?${new URLSearchParams({ template: 'tip.md', title, body })}`;
  if (url.length > 7000) throw new Error('Odkaz je příliš dlouhý. Zkraťte prosím návrh.');
  return url;
}
