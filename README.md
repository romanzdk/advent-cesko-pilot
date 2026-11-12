# Advent v Česku 2026 — pilot tří krajů

Samostatný sezonní pilot, ne úplný katalog republiky. Období **20. 11.–24. 12. 2026**. Výběr měst: Plasy, Černošín, Semily, Jilemnice, Rajhrad a Kuřim. Veřejný web: https://romanzdk.github.io/advent-cesko-pilot/ .

Původní [Mnichovice a okolí](https://romanzdk.github.io/advent-mnichovice/) jsou samostatný projekt. Tento repozitář nemění jejich web, plánovač, osobní kalendář ani pozvánky.

## Co je funkční

- Mobilní seznam a mapa Leaflet/OpenStreetMap, filtry podle kraje, města, termínu a typu; detail a jednotlivý ICS export.
- Šest konfigurovaných zdrojů ve třech krajích, čtyři CMS adaptéry: Galileo, Vismo, WordPress a Drupal.
- Omezený deterministický sběr: nejvýše dvě stránky výpisu a čtrnáct detailů na zdroj, objevování nových odkazů, nikoli jen statický seznam známých událostí.
- SQLite evidence, stabilní ID, sémantická detekce změn, HTTP cache s ETag/Last-Modified a kontrolou hashů, respektování robots.txt a prodlev hostitelů.
- Zdroje a stav pokrytí jsou na webu viditelné. Nejasná data a lokality se nezveřejňují jako potvrzené akce; zůstávají ve frontě ke kontrole.
- Veřejná data jsou výslovně oddělená od interní databáze, HTTP cache a prvotních HTML podkladů. Automatické přidávání republikových akcí do osobního kalendáře není zapnuté.

## Ověření pilotu a známé mezery

První průzkum ověřil 18 detailů v primárních zdrojích. Živý sběr našel další odpovídající události. Přesné aktuální počty a metriky jsou v `site/coverage.json`; nelze z nich vyvozovat úplnost kraje.

Semily aktuálně v robots.txt nepovolují automatické načítání sledovaných adres. Sběrač zákaz respektuje, nepoužívá soukromé HTML podklady k předstírání úspěšného živého běhu a na webu ukazuje zdroj jako nedostupný. Datum poslední kontroly není totéž co datum posledního úspěchu.

Další vyřazené kandidáty tvoří především místní části Plas bez samostatně ověřené mapové lokality, termíny mimo sledované období a zájezd, u kterého nelze vydávat místo odjezdu za místo vánočního programu. Fronta zatím vyžaduje lidskou kontrolu; není to automatické kompletní řešení celé ČR. Ceny mohou zůstat neznámé a odkazy nepotvrzují volná místa.

Body v mapě představují ověřené **orientační středy obcí**, ne přesné vstupy. Původ poloh je v `data/locations.json`. U vícedenních akcí krajní termíny neznamenají nepřetržité ani každodenní otevření.

## Opakování sběru

Python 3, pouze standardní knihovna:

```sh
python3 scripts/collector.py --registry data/sources.json \
  --db private/events.sqlite --cache private/http-cache \
  --output site --locations data/locations.json
python3 scripts/validate_public.py site
```

Interní databáze a cache zůstávají lokálně pod ignorovaným `private/`. Při nedostupnosti zdroje se poslední dobrá data zachovají, ale zdroj se označí chybovým stavem. Při novém nejednoznačném obsahu se starý záznam stáhne do kontroly; odstranění stránky samo o sobě neznamená zrušení akce.

Tento pilot se zatím aktualizuje explicitním spuštěním sběru a publikací tří veřejných JSON souborů. Není zde plošný každodenní AI průzkum ani nový sezonní plánovač. Denní lokální hlídání Mnichovic tím není dotčené.

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

Před přidáním dalších krajů doporučujeme vyřešit blokovaný zdroj, geografickou frontu a ověřit opakovatelnost během více dnů. Zkušenost šesti zdrojů zatím neopravňuje slibovat stejné náklady či úplnost pro celou republiku.
