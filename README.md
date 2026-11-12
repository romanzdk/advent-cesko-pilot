# Advent v Česku

**Adventní akce na jedné mapě, s odkazem na pořadatele a přiznanými nejistotami.**

Sezonní projekt pro Vánoce 2026. Sbírá rozsvěcení stromků, mikulášské nadílky, jarmarky, tvoření a další adventní programy z obecních a pořadatelských kalendářů. Z veřejných podkladů vytváří přehled, ve kterém lze vybírat podle místa, termínu a typu akce.

**[Otevřít živou mapu](https://romanzdk.github.io/advent-cesko-pilot/)** · [Architektura](#architektura) · [Jak fungují data](#od-oznámení-k-akci-na-mapě) · [Technická dokumentace](docs/operations.md)

[![Kontroly a nasazení](https://github.com/romanzdk/advent-cesko-pilot/actions/workflows/deploy.yml/badge.svg)](https://github.com/romanzdk/advent-cesko-pilot/actions/workflows/deploy.yml)

![Skutečná desktopová verze Adventu v Česku: filtry, chronologický seznam a mapa vybraných míst](docs/assets/desktop.png)

*Screenshot nasazeného webu z 12. listopadu 2026 po rozšíření na šest krajů. Nejde o návrh rozhraní ani ukázková data.*

## Proč projekt vznikl

Termíny adventních akcí bývají rozptýlené mezi obecními kalendáři, kulturními centry a samostatnými pozvánkami. Každý web zapisuje čas a místo jinak. Někde chybí hodina, jinde je důležitý údaj jen v textu nebo se liší místo akce od sídla pořadatele.

Projekt začal hledáním rozsvícení stromků a mikulášských akcí v okolí Mnichovic. Tento samostatný pilot ověřuje, zda lze stejný typ informací opakovaně sbírat i v dalších krajích, aniž by každá aktualizace potřebovala nový ruční průzkum nebo AI.

Cílem je usnadnit výběr akce a zachovat možnost ověřit si ji u pořadatele. Projekt zatím neslibuje úplný kalendář České republiky.

## Co na webu najdete

- Chronologický seznam a mapu s přepínáním zobrazení na mobilu.
- Hledání a kombinovatelné filtry podle kraje, obce, typu akce a termínu, včetně dneška a tohoto víkendu.
- Datum, zveřejněný čas, místo, známé vstupné, informace o rezervaci a přímý zdroj u každé položky.
- Viditelné upozornění na neznámý čas, omezené zaměření programu nebo pouze orientační polohu.
- Navigaci do obce a export jednotlivé akce do kalendáře ve formátu ICS.
- Rozbalovací přehled sledovaných zdrojů, jejich dostupnosti, posledních kontrol a položek ke kontrole či mimo rozsah.

### Na telefonu

Seznam je výchozí mobilní zobrazení; mapu lze otevřít samostatně. Na snímku je použitý filtr rozsvícení stromů.

<img src="docs/assets/mobile.png" alt="Skutečná mobilní verze s filtrem rozsvícení stromů a akcí v Babině, místní části Plas" width="330">

*Mobilní screenshot z 12. listopadu 2026. Rozhraní používá stejná veřejná data jako desktop.*

## Rozsah současného pilotu

Sledované akce spadají do období **20. listopadu až 24. prosince 2026**.

- **Plzeňský kraj:** Plasy, Černošín a ověřené místní části Plas: Babina, Horní Hradiště, Žebnice a Nebřeziny.
- **Liberecký kraj:** Jilemnice a pořadatelský výběr z Kulturního centra Semily / KC Golf.
- **Jihomoravský kraj:** Rajhrad a Kuřim.
- **Středočeský kraj:** Beroun a Hořovice.
- **Jihočeský kraj:** Soběslav a pořadatelský kalendář IKS Třeboň.
- **Kraj Vysočina:** Telč a Humpolec.

**Stav k 12. listopadu 2026 po rozšíření: 57 publikovaných akcí, 12 zdrojů, 6 krajů.** Dalších 37 kandidátů zůstává k ověření, zejména kvůli dosud neověřenému místu nebo více termínům. Všech 12 zdrojů se podařilo načíst; stav „částečně“ u nových zdrojů přiznává tuto kontrolní frontu, nikoli kompletní pokrytí. Je to datovaný snímek pilotu, ne trvale aktuální počítadlo. Poslední výsledky a rozsah kontrol najdete přímo na webu v sekci *Zdroje a pokrytí*.

Výběr několika měst neznamená pokrytí celého kraje. Původní [mapa Mnichovic a okolí](https://romanzdk.github.io/advent-mnichovice/) má vlastní repozitář i hlídání a zůstává oddělená.

## Architektura

Projekt odděluje sběr dat od jejich zobrazování. Python běží na serveru; návštěvník dostává hotový statický web z GitHub Pages. Prohlížeč nemá přístup k interní databázi ani ke sběrači.

![Architektura: veřejné zdroje a konfigurace vstupují do Python sběrače se soukromou SQLite a HTTP cache; validovaná veřejná data se přes GitHub Actions dostávají na GitHub Pages](docs/assets/architecture.png)

[Zdroj schématu v samostatném HTML/SVG](docs/architecture.html)

### Od oznámení k akci na mapě

1. **Registr určí zdroje a rozsah.** `data/sources.json` obsahuje kalendáře, rozpoznávané detailní odkazy, adaptéry a sezonní okno. Samostatná konfigurace drží ověřené mapové polohy.
2. **Sběrač načte veřejné stránky.** Hledá nové detailní odkazy, respektuje robots.txt, omezuje počet požadavků a používá HTTP cache s ETag, Last-Modified a kontrolou otisků obsahu.
3. **Adaptéry sjednotí údaje.** Přednost má skutečný JSON-LD `Event`; další adaptéry čtou známé HTML šablony. Datum musí mít doložený rok, místo musí odpovídat lokalitě. Nejasnosti zůstávají k ověření.
4. **SQLite zachová stav a původ údajů.** Stabilní identifikátory a otisky věcného obsahu rozlišují nové, změněné a nezměněné položky. Záznamy uchovávají zdroj a pozorování důležitých polí.
5. **Vznikne veřejná projekce.** `events.json` slouží seznamu a mapě, `coverage.json` popisuje pokrytí a poslední běh, `review.json` obsahuje omezený veřejný přehled nejasných kandidátů. Interní databáze a zachycené stránky zůstávají mimo repozitář.
6. **Publisher zkontroluje a ověří nasazení.** Validuje veřejné soubory a publikuje pouze tři povolené JSON. Push do `main` spustí testy a nasazení adresáře `site/`. Úspěch potvrdí až kontrola vzdáleného commitu, výsledku GitHub Actions a skutečných dat na webu.

### Použité technologie

| Část | Technologie | Důvod |
| --- | --- | --- |
| Sběr a zpracování | Python, standardní knihovna | Běžný sběr nevyžaduje AI ani externí Python balíčky. |
| Evidence | SQLite a lokální HTTP cache | Historie, původ údajů a opakovatelné porovnávání změn. |
| Web | HTML, CSS, JavaScript | Statický frontend bez build kroku a aplikačního API. |
| Mapa | Leaflet a OpenStreetMap | Mapový přehled s uvedenou přesností polohy. |
| Publikace | Git, GitHub Actions, GitHub Pages | Kontroly a samostatné statické nasazení. |
| Spouštění | Hermes v režimu `no_agent` | Časovač volá Python skript bez LLM. |

## Jak projekt zachází s nejistotou

Důležitější než počet bodů na mapě je to, co zdroj skutečně potvrzuje.

- **Neznámý čas se nedopočítává.** Na webu zůstane neznámý. V ICS je neznámá hodina poznámkou data; pokud je znám začátek, ale ne konec, export výslovně označí orientační hodinovou délku.
- **Mapa nepředstírá přesný vstup.** Současné body představují orientační středy obcí či místních částí. Lokalita akce se neodvozuje jen ze sídla pořadatele.
- **Vícedenní interval není otevírací doba.** Krajní data neznamenají nepřetržité ani každodenní otevření.
- **Nedostupnost není zrušení akce.** Při chybě načtení zůstávají poslední dobrá data a zdroj dostane chybový stav. Nově načtený rozporný obsah naopak stáhne položku do kontroly.
- **Rozsah zdrojů je viditelný.** Městský kalendář Semil automatické načítání sledovaných adres nepovoluje. Pilot místo jeho obcházení čte přímo povolený web KC Golf a tento rozdíl uvádí v pokrytí.
- **Známé vyřazení není nevyřešený problém.** Programy mimo období a zájezdy se evidují zvlášť; místo odjezdu se nezaměňuje za místo vánočního programu.

Zveřejněná cena ani odkaz na rezervaci nepotvrzují volná místa. Před cestou je rozhodující aktuální informace pořadatele.

## Automatizace a ověření

Denní aktualizace je nastavena na **08:30 Europe/Prague od 13. listopadu do 24. prosince 2026**. Publisher má zámek proti souběhu, kontroluje čistotu pracovní kopie a pevný cílový repozitář. Po konci sezony nic nesbírá ani nepublikuje. Běžný úspěch je tichý, chyba se hlásí správci.

Celý průchod sběrem, publikací a ověřením skutečného webu byl spuštěn přes stejný skriptový launcher jako v plánovači. K datu uvedeného snímku byly naplánované pravidelné běhy teprve před prvním ranním spuštěním; ruční ověření není vydáváno za několikadenní provoz.

Po zdrojové kontrole a dvou závěrečných živých sběrech z 12. listopadu 2026 pilot obsahuje **20 nových akcí**, původních 37 zůstalo věcně beze změny. Opakovaný průchod potvrdil **57 nezměněných akcí**, bez nových položek či duplicit. Sběrač vykázal **0 AI volání**; tento údaj se nevztahuje k úvodní rešerši a vývoji. Skutečnou délku běhu a počty HTTP požadavků ukazuje sekce *Zdroje a pokrytí*.

Ověření zahrnuje:

- **58 Python testů:** parsování podkladů včetně tří nových HTML šablon, registr zdrojů, práce s daty, výpadky, geografická přiřazení a bezpečné publikování v dočasných Git repozitářích.
- **28 JavaScriptových a prohlížečových testů:** šestikrajové filtry, kalendář, mobilní rozhraní, chybové stavy a bezpečné vykreslení.
- Kontrolu skutečně nasazené desktopové i mobilní verze, mapových dlaždic a stažení ICS.

CI provádí offline Python testy, čisté JS testy, validaci veřejných dat a kontrolu syntaxe. Úplná sada Chromium testů se spouští lokálně. Počty testů popisují ověřený stav k 12. listopadu 2026.

## Co je hotové a co následuje

Pilot má funkční sběr z uvedených dvanácti zdrojů, oddělenou interní evidenci, veřejný web a sezonní publikační úlohu. Nečte Facebook, nezpracovává obecně všechny plakáty a PDF a nevytváří automatické pozvánky do osobního kalendáře.

Validátor odvozuje zdroje, kraje a přiřazení událostí z registru; rozhraní ukazuje skutečný rozsah z dat. U šesti nových zdrojů se automaticky přijímají pouze ověřené názvy míst v příslušné obci. Nové místo čeká na kontrolu, aby se například program v Berouně nezobrazil jako akce v Hořovicích.

Další krok je ověřovat zadržené kandidáty a doplňovat místa ve stávajících krajích; ostatní kraje ČR zatím nejsou zahrnuté. Rozšíření vždy vyžaduje zdrojovou a geografickou kontrolu, nestačí přidat název kraje do filtru.

## Orientace v repozitáři

```text
scripts/collector.py       sběr, adaptéry, evidence a veřejný export
scripts/publish_daily.py   validovaná publikace a ověření webu
scripts/validate_public.py kontrola veřejné projekce
data/                     registr zdrojů a mapové polohy
site/                     frontend a publikovaná data
tests/                    Python testy a přenositelné faktické podklady
tests-ui/                 JS a izolované prohlížečové testy
docs/                     architektura, screenshoty a provozní dokumentace
private/                  lokální stav; ignorovaný a nepublikovaný
```

[Provoz a ověřovací příkazy](docs/operations.md) · [Podrobnosti sběrače](scripts/COLLECTOR.md)

## Autor a podmínky použití

Projekt připravil **[Roman Žydyk](https://github.com/romanzdk)**.

Vlastní kód projektu není open source. **Všechna práva vyhrazena**, v rozsahu práv chráněných zákonem a náležejících uvedenému nositeli práv. Veřejný repozitář není obecným svolením ke spuštění vlastní kopie, úpravám nebo šíření. Běžné používání veřejné mapy je dovoleno; zachována jsou práva podle podmínek GitHubu a zákonné výjimky. Úplné podmínky jsou v [LICENSE](LICENSE).

Cizí komponenty a data si ponechávají vlastní podmínky. Leaflet zůstává pod [BSD 2-Clause](site/vendor/LEAFLET-LICENSE.txt); práva k podkladům pořadatelů a [OpenStreetMap](https://www.openstreetmap.org/copyright) se tím nemění.
