# Přenosné podklady nových zdrojů

Malé kurátorované sémantické fragmenty z primárních detailů ověřených 12. 11. 2026, nikoli úplné stažené stránky. Původní HTTP bajty a cache zůstávají výhradně v ignorovaném `private/` izolovaného výzkumného worktree.

- `galileo.json`: Nejdek — rozsvícení stromu; Dobruška — vánoční jarmark. Každý případ obsahuje přesnou primární URL a očekávaná věcná pole.
- `hranice.html`: https://kultura-hranice.cz/akce/adventni-koncert-s-zaves-2/ — označené řádky termínu, začátku, místa a celého vstupného; omezený vlastní popis. Tato akce testuje formát, není tvrzením, že se vejde do prvních 14 detailů aktuálních výpisů.
- `wpem.html`: https://www.muzeumusti.cz/kalendar-akci/advent-v-muzeu-6/ — skutečný nestandardní JSON-LD `Location` a mezera v timestampu, cenový blok „od 200 Kč (materiál je v ceně)“. Text popisu je zkrácen na podstatné podmínky; nejde o plný capture.
- `visitzlin.html`: https://visitzlin.eu/kalendar-akci/adventni-zlin-2026 — skutečně označený adventní interval a místo; oddělená narativní povánoční část. Hodiny nejsou vymyšlené.
- `wave2-galileo.json`: přesné primární URL Radotína a Štítiny, původní označené termíny/místa a krátké věcné fragmenty. Skutečná zbrojnice i kostel se ověřují mimo fixture podle živých detailů; fixture není úplný katalog.
- `lanskroun.html`: https://www.kclanskroun.cz/festival/adventni-lanskroun/ — označený interval `29. 11 - 20. 12. 2026` a krátký popis náměstí. Historická zmínka roku 2024 není časovým zdrojem; footer je výslovně syntetický rušivý kontext. Živá discovery jde přes `/festivaly/`, ne bootstrap.

Rušivé `aside`/`footer` bloky a mutace cen, chybějících roků, neplatných hodin, vloženého JSON-LD, štítků a neúplných intervalů jsou výslovně **syntetické negativní testy**, nikoli publikované akce nebo důkaz živé dostupnosti.

Testy používají reálný parser, registry a `FixtureClient` s dočasným SQLite. Všechny nové zdroje mají prázdné seeds a detaily se v integračních testech musí najít z výpisového odkazu. Testy nevyžadují `private/`, síť, přihlášení ani produkční databázi. Živá discovery a audit všech přijatých akcí jsou popsány zvlášť v `docs/national-source-audit.md` a `docs/national-event-audit.md`.
