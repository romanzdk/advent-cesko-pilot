<p align="center">
  <img src="site/social-preview.png" alt="Advent v Česku 2026 — sezonní mapa veřejných akcí" width="100%">
</p>

# Advent v Česku

**Najděte svůj adventní program. S odkazem přímo na pořadatele.**

Sezonní mapa adventních a vánočních akcí pro **20. listopadu – 24. prosince 2026**. Rozsvěcení stromků, mikulášské nadílky, jarmarky, koncerty i tvoření na jednom místě — s přiznanými nejistotami a ověřitelným původem údajů.

[**Otevřít mapu**](https://kamnaadvent.cz/) · [Poslat tip](https://github.com/romanzdk/advent-cesko-pilot/issues/new?template=tip.md) · [Veřejná hlášení](https://github.com/romanzdk/advent-cesko-pilot/issues?q=is%3Aissue) · [Provozní dokumentace](docs/operations.md)

[![Kontroly a nasazení](https://github.com/romanzdk/advent-cesko-pilot/actions/workflows/deploy.yml/badge.svg)](https://github.com/romanzdk/advent-cesko-pilot/actions/workflows/deploy.yml)
![Sezóna 2026](https://img.shields.io/badge/sez%C3%B3na-2026-244b3c?style=flat)
[![Proprietární licence](https://img.shields.io/badge/licence-propriet%C3%A1rn%C3%AD-62695e?style=flat)](LICENSE)

> **Dostupnost webu:** poslední kontrola 12. listopadu 2026 potvrdila nasazení na GitHub Pages, ale DNS vlastní domény `kamnaadvent.cz` ještě nefungovalo. GitHub hlášení jsou dostupná nezávisle na doméně.

## Co mapa nabízí

- **Výběr podle vás.** Kombinace kraje, obce, typu akce a termínu, textové hledání, dnešek, víkend i vlastní rozsah dat Od–Do. Rozsah zahrnuje oba krajní dny a překrývající se vícedenní akce; lze zadat i pouze jednu hranici v rámci sezóny.
- **Seznam i mapa.** Chronologický přehled na telefonu, prostorové zobrazení na větší obrazovce. Barvy bodů rozlišují typ akce; legenda vysvětluje barvy a neutrální bod označuje více různých typů na jednom místě.
- **Údaje se zdrojem.** Datum, zveřejněný čas, místo, známé vstupné, rezervace a přímý odkaz na pořadatele.
- **Kalendář a navigace.** Samostatný ICS export každé akce a trasa v Google Maps; orientační polohy jsou výslovně označené. Mapový podklad na webu zůstává OpenStreetMap.
- **Viditelné pokrytí.** Sledované zdroje, poslední kontroly a položky čekající na ověření nejsou skryté.
- **Veřejné tipy.** Návrh obce, odkazu nebo opravy přes GitHub; existující hlášení lze prohledat a doplnit komentářem. Odeslání vyžaduje účet GitHub a zařazení do mapy není automatické.

## Ukázka rozhraní

![Desktop: filtry, chronologický seznam a mapa vybraných míst](docs/assets/desktop.png)

<details>
<summary>Zobrazení na telefonu</summary>

<img src="docs/assets/mobile.png" alt="Mobilní přehled s filtrem rozsvícení stromů" width="330">

</details>

*Skutečné screenshoty veřejného webu z 12. listopadu 2026 po rozšíření na šest krajů. Zachycují tehdejší verzi rozhraní, nikoli aktuální počítadlo akcí. Úvodní sdílecí obrázek je samostatná značková ilustrace.*

## Pokrytí a rozsah

**Datovaný stav k 12. listopadu 2026: 78 akcí · 12 zdrojů · 6 krajů.**

| Kraj | Sledované obce a pořadatelé |
| --- | --- |
| Plzeňský | Plasy, Černošín a ověřené místní části Plas |
| Liberecký | Jilemnice, KC Golf Semily |
| Jihomoravský | Rajhrad, Kuřim |
| Středočeský | Beroun, Hořovice |
| Jihočeský | Soběslav, IKS Třeboň |
| Vysočina | Telč, Humpolec |

Jde o **výběr zdrojů, ne úplný kalendář krajů nebo celé ČR**. Aktuální stav načítání a rozsah kontrol najdete na webu v panelu *Zdroje a pokrytí*. Dvě položky čekají na dořešení termínu či více samostatných představení; [podrobnosti kontroly](docs/operations.md#ruční-kontrola-kandidátů).

## Jak vznikají data

![Architektura sběru, validace a statické publikace](docs/assets/architecture.png)

**Veřejné kalendáře → Python adaptéry → SQLite a cache → validovaná veřejná data → GitHub Pages.**

Sběrač respektuje robots.txt, omezuje požadavky, používá HTTP cache a rozpoznává změny obsahu. Nejasné údaje ponechává k ověření. Interní databáze a zachycené podklady se nepublikují; prohlížeč dostává pouze veřejnou projekci.

Běžná aktualizace je deterministická, **bez LLM volání**. Python běží na serveru, GitHub Actions provádí kontroly a nasazuje statický web. Denní plán je nastavený na **08:30 Europe/Prague, 13. listopadu – 24. prosince 2026**; po konci sezony publisher nic nesbírá ani nepublikuje. Ručně ověřené průchody nejsou vydávány za několikatýdenní provoz.

**Technologie:** Python · SQLite · HTML/CSS/JavaScript · Leaflet · OpenStreetMap · GitHub Actions / Pages.

[Architektura ve větším formátu](docs/architecture.html) · [Sběrač a formáty zdrojů](scripts/COLLECTOR.md) · [Provoz, validace a obnova](docs/operations.md)

## Důvěryhodnost před počtem bodů

- **Neznámý čas se nevymýšlí.** Datum bez hodiny není tvrzení, že program trvá celý den.
- **Střed obce není přesný vstup.** U orientačních bodů je přesnost přiznaná.
- **Rozsah dat není otevírací doba.** Vícedenní interval neznamená nepřetržitý program.
- **Výpadek není zrušení.** Poslední dobrá data lze zachovat při chybě sítě; nový rozporný obsah naopak vede ke kontrole.
- **Odkaz není rezervace.** Cena ani rezervační stránka nepotvrzují zbývající kapacitu. Před cestou rozhoduje pořadatel.

Projekt neobchází blokované kalendáře a neslibuje obecné zpracování všech plakátů, PDF nebo Facebooku.

## Kvalita a orientace v kódu

**75 Python testů a 55 JavaScriptových/prohlížečových testů** pokrývá adaptéry, validaci, geografii, bezpečnou publikaci, filtry včetně vlastního rozsahu dat, kalendář, mobilní rozhraní, tipy, přístupnou patičku i sdílecí metadata. Počty popisují ověřovaný stav k 12. listopadu 2026. CI běží offline; úplné Chromium testy se spouštějí lokálně.

```text
scripts/     sběr, adaptéry, validace a publisher
data/        registr zdrojů a ověřené mapové polohy
site/        statický frontend, veřejná data a sdílecí obrázek
tests/       Python testy a přenositelné faktické podklady
tests-ui/    JS testy a izolované prohlížečové scénáře
docs/        architektura, screenshoty, vizuální podklady a provoz
```

## Autor a licence

**[Roman Žydyk](https://romanzdk.com/)** · [GitHub](https://github.com/romanzdk)

Vlastní kód není open source. **Všechna práva vyhrazena** v rozsahu práv chráněných zákonem a náležejících autorovi. Běžné používání veřejné mapy je dovoleno; zachována jsou práva podle podmínek GitHubu a zákonné výjimky. Veřejný repozitář není obecnou licencí k úpravám, šíření nebo vlastnímu provozu — úplné podmínky jsou v [LICENSE](LICENSE).

Cizí komponenty a data mají vlastní podmínky: [Leaflet / BSD 2-Clause](site/vendor/LEAFLET-LICENSE.txt), [OpenStreetMap](https://www.openstreetmap.org/copyright) a podklady jednotlivých pořadatelů. Obrys ČR v propagační ilustraci pochází z [Natural Earth](https://www.naturalearthdata.com/about/terms-of-use/) (public domain).
