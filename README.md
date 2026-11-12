# Advent v Česku 2026 — pilot tří krajů

Samostatný sezonní pilot, ne úplný katalog republiky. Období **20. 11.–24. 12. 2026**. Výběr měst: Plasy, Černošín, Semily, Jilemnice, Rajhrad a Kuřim; navíc ověřené místní části Plas Babina, Horní Hradiště, Žebnice a Nebřeziny. Veřejný web: https://romanzdk.github.io/advent-cesko-pilot/ .

Původní [Mnichovice a okolí](https://romanzdk.github.io/advent-mnichovice/) jsou samostatný projekt. Tento repozitář nemění jejich web, plánovač, osobní kalendář ani pozvánky.

## Licence a použití

**Vlastní kód projektu není open source. Všechna práva vyhrazena — Roman Žydyk, 2026**, v rozsahu práv chráněných zákonem a náležejících tomuto nositeli práv. Veřejné zpřístupnění repozitáře není obecným svolením k provozování vlastní kopie, používání sběrače, úpravám ani dalšímu šíření; pro takové využití je nutný předchozí písemný souhlas, pokud je již neopravňuje zákon nebo podmínky GitHubu. Úplné vymezení je v souboru [LICENSE](LICENSE).

Běžné používání veřejně nasazené mapy, včetně jejího zobrazení v prohlížeči, navigace a jednotlivého exportu do kalendáře, je výslovně dovolené. Zachována zůstávají práva k prohlížení a forkování veřejného repozitáře podle podmínek GitHubu i zákonné výjimky. Nejde o technickou ochranu proti stažení kódu.

Omezení se nevztahuje na cizí komponenty a jejich licence ani nepřisvojuje práva k veřejným faktům či podkladům pořadatelů. **Leaflet zůstává pod BSD 2-Clause**; původní znění je v [site/vendor/LEAFLET-LICENSE.txt](site/vendor/LEAFLET-LICENSE.txt). Data a mapové podklady [OpenStreetMap](https://www.openstreetmap.org/copyright) a další cizí materiály si ponechávají své vlastní podmínky.

## Co je funkční

- Mobilní seznam a mapa Leaflet/OpenStreetMap, filtry podle kraje, města, termínu a typu; detail a jednotlivý ICS export.
- Šest konfigurovaných zdrojů ve třech krajích: Galileo, WordPress, Drupal a strukturované JSON-LD Event; zachovaná regresní podpora Vismo.
- Omezený deterministický sběr: nejvýše dvě stránky výpisu a čtrnáct detailů na zdroj, objevování nových odkazů, nikoli jen statický seznam známých událostí.
- SQLite evidence, stabilní ID, sémantická detekce změn, HTTP cache s ETag/Last-Modified a kontrolou hashů, respektování robots.txt a prodlev hostitelů.
- Zdroje a stav pokrytí jsou na webu viditelné. Nejasná data a lokality se nezveřejňují jako potvrzené akce; zůstávají ve frontě ke kontrole.
- Veřejná data jsou výslovně oddělená od interní databáze, HTTP cache a prvotních HTML podkladů. Automatické přidávání republikových akcí do osobního kalendáře není zapnuté.

## Ověření pilotu a známé mezery

První průzkum ověřil 18 detailů v primárních zdrojích. Živý sběr našel další odpovídající události. Přesné aktuální počty a metriky jsou v `site/coverage.json`; nelze z nich vyvozovat úplnost kraje.

Původní městský kalendář Semil v robots.txt nepovoluje automatické načítání sledovaných adres. Sběrač zákaz respektuje; místo něj používá přímo povolený web Kulturního centra Semily / KC Golf. Pokrytí je proto pořadatelský výběr, nikoli kompletní městský kalendář. Datum poslední kontroly není totéž co datum posledního úspěchu.

Šest původně nejasných akcí v místních částech Plas je vyřešených: samostatné OSM polohy, původní názvy a přesné URL+datum+místo z primárních stránek. Při změně místa nebo data přestává ruční geografické přiřazení platit a položka jde do kontroly. Termíny mimo sledované období a zájezdy se počítají odděleně jako vyloučené, ne jako nevyřešené kandidáty. Fronta dosud neznámých/rozporných údajů nadále vyžaduje lidskou kontrolu. Ceny mohou zůstat neznámé a odkazy nepotvrzují volná místa.

Body v mapě představují ověřené **orientační středy obcí či místních částí**, ne přesné vstupy. Původ poloh je v `data/locations.json`. U vícedenních akcí krajní termíny neznamenají nepřetržité ani každodenní otevření.

## Opakování sběru

Python 3, pouze standardní knihovna:

```sh
python3 scripts/collector.py --registry data/sources.json \
  --db private/events.sqlite --cache private/http-cache \
  --output site --locations data/locations.json
python3 scripts/validate_public.py site
```

Interní databáze a cache zůstávají lokálně pod ignorovaným `private/`. Při nedostupnosti zdroje se poslední dobrá data zachovají, ale zdroj se označí chybovým stavem. Při novém nejednoznačném obsahu se starý záznam stáhne do kontroly; odstranění stránky samo o sobě neznamená zrušení akce.

Denní sezonní aktualizace běží v **08:30 Europe/Prague**, od 13. 11. do 24. 12. 2026, přes samostatnou no-agent úlohu Hermes. Sběrač i publikace běží bez AI. Skript `scripts/publish_daily.py` má vlastní zámek, kontrolu čistého checkoutu a pevného repozitáře/větve, validaci veřejných souborů, omezený commit jen tří veřejných JSON a ověření vzdáleného commitu, úspěšného Pages workflow i skutečného webu. Běžný úspěch je tichý; chyba se hlásí. Pevná kontrola sezony znemožní sběr po 24. 12. 2026 i při opožděném běhu. Denní lokální hlídání Mnichovic tím není dotčené.

Pro ruční ověřenou aktualizaci z čistého checkoutu: `python3 scripts/publish_daily.py`. Read-only kontrola připravenosti: `python3 scripts/publish_daily.py --check`. Skript nikdy automaticky neopravuje nesouvisející pracovní změny. Pokud přerušený sběr nechá rozpracované veřejné soubory nebo selže zápis vlastnického stavu hned po commitu, další běh bezpečně skončí chybou; obnovu proveďte ručně až po kontrole konkrétního diffu. Nepoužívejte plošný reset/stash vedle cizí práce. Známý vlastní commit po chybě push/nasazení se ověří a zkusí znovu bez dalšího sběru či duplicitního commitu.

## Testy

```sh
python3 -m unittest discover -s tests -v
node --test tests-ui/helpers.test.mjs tests-ui/pilot.test.mjs
npm install --prefix tests-ui
npm test --prefix tests-ui
```

Playwright může pro novou instalaci vyžadovat stažení Chromium. Browser testy mají vlastní izolovaný prohlížeč a fixture server, ne uživatelovu sdílenou relaci. CI provádí offline Python testy, čisté JS testy, validaci veřejné projekce a kontrolu syntaxe; úplné Chromium testy byly spuštěny lokálně. Přenositelné HTML testy obsahují jen krátké faktické fragmenty a jsou označené v `tests/fixtures/README.md`; původní zachycené stránky nejsou veřejnou součástí repozitáře.

## Nasazení

Push do `main` projde kontrolami a nasadí pouze adresář `site/` přes samostatné GitHub Pages. Nikdy se nenahrává `private/`, databáze ani cache. Není zapotřebí release ani placená služba. Náklady na úvodní rešerši a vývoj nejsou měřené; metrika `aiCalls: 0` se vztahuje pouze k deterministickému sběrači, nikoli k vývoji projektu.

Před přidáním dalších krajů doporučujeme ověřit přirozené denní běhy a změny během více dnů. Zkušenost šesti zdrojů zatím neopravňuje slibovat stejné náklady či úplnost pro celou republiku.
