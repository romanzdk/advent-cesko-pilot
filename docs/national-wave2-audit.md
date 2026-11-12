# Druhá dávka primárních zdrojů — 12. 11. 2026

Navazuje na první dávku PR #1, nikoli na nový projekt. Výchozí registr programově spočítán: **17 zdrojů / 11 krajů**; baseline akcí jsou skutečné `final-4` výsledky **107**, nikoli veřejný historický snapshot 78. Prvních 17 definic i všech 107 věcných záznamů zachováno. Větev byla z čistého stavu rebased na `origin/main` `a3d320f`, včetně souběžných vlastních datumů, clear buttonu a příběhu v patičce. Otevřené visitor issues byly před průzkumem znovu načteny: žádné.

Nový registr má **20 zdrojů / zastoupení všech 14 krajů**, stále `complete:false`, jen sezonu **20. 11.–24. 12. 2026**. Nejde o úplné pokrytí ČR, krajů ani obcí. Offline replay i oba finální živé sběry dávají **113 akcí, čistý přírůstek této dávky 6**; celý PR proti původním 78 přidává 35. Výsledky nejsou nasazené.

## Primární zdroje a skutečná discovery

| Kraj | Ověřený primární výpis a detail | Dostupnost / rozhodnutí |
| --- | --- | --- |
| Hlavní město Praha | https://www.praha16.eu/volny-cas/kalendar-akci/ a skutečný stránkovací odkaz `?page=1`; např. https://www.praha16.eu/volny-cas/kalendar-akci/i-adventni-koncert-26167_706cs.html | Oba výpisy a všechny sezonně nalezené detaily načteny vlastním robots-aware HTTP klientem. Existující Galileo, bez seeds. Přijaty čtyři programy na třech konkrétně ověřených radotínských místech. Není to centrální Praha ani ostatní městské části. |
| Pardubický kraj | https://www.kclanskroun.cz/festivaly/ → https://www.kclanskroun.cz/festival/adventni-lanskroun/ | Skutečný odkaz z festivalového výpisu, bez seeds, HTTP klient načetl obě stránky. Nový úzký adaptér `lanskroun`; celý označený interval `29. 11 - 20. 12. 2026`, výslovný společný rok v témže poli. Jeden souhrnný festival, ne 22 vymyšlených denních akcí. |
| Moravskoslezský kraj | https://www.stitina.cz/aktualne/kalendar-akci/ → https://www.stitina.cz/aktualne/kalendar-akci/vitame-advent-1636_167cs.html | Výpis a oba nalezené sezonní detaily načteny HTTP klientem po robots. Stávající Galileo, bez seeds. Přijat program v parku v ulici Hlavní, skutečně Štítina v okrese Opava; nikoli Ostrava nebo Jeseník nad Odrou. |

U každého nového zdroje zůstává limit **2 výpisy / 14 detailů**, bez změny frekvence, per-host delay, TLS kontroly nebo AI fallbacku. Živá dostupnost není vyvozena z vyhledávače nebo z portable fixture. Lanškroun používá jen jediný skutečný výpis; limit nezvyšuje.

## Alternativy a blokace

- Praha-Zbraslav: skutečný primární kandidát https://www.mc-zbraslav.cz/ap — **robots zakazuje URL**, obsah nečten. Soukromý ŽIJE.eu sloužil jen k discovery, nebyl zaregistrován jako primární obecní zdroj. Radotín je nezávislá povolená alternativa.
- Prague City Tourism s `Crawl-delay:600`, magistrátní TLS chyba a nepodporovaná šablona Dolních Počernic jsou doloženy první dávkou. Nebyly slepě opakovány, TLS verify nebylo vypnuto a robots nebyly obcházeny.
- Česká Třebová: https://www.ceska-trebova.cz/ — **robots zakazuje URL**, obsah nečten. Sekundární texty a jejich titulky 2026 nebyly použity k automatickému přijetí termínů.
- Moravská Třebová (Pardubický kraj, nikoli Moravskoslezský): https://www.ksmt.cz/akce/rozsviceni-vanocniho-stromu-5/ — detail skutečně načten, explicitně 28. 11. 2026, 15:00–19:00, Náměstí T. G. Masaryka; strom 17:45. Jiná šablona bez zaregistrovaného adaptéru, další implementace kvůli rozpočtu nezahájena. Přednost dostal funkčně ověřený Lanškroun.
- Jeseník nad Odrou / Blahutovice a samotná homepage Ostravských Vánoc nebyly přejmenovány na nově integrované zdroje. Stále platí předchozí geografická výhrada; Štítina je jiné, prokazatelně místní řešení.

## Audit všech šesti nově přijatých akcí

Cena neuvedena neznamená zdarma. Neuvedený konec není odhadovaná délka ani celodenní program. Všechny nové polohy jsou pouze orientační středy / body části obce, nikoli přesné místo akce.

| Akce a primární detail | Obec / ověřené místo | Datum / interval 2026 | Publikovaný čas | Cena / interpretace |
| --- | --- | --- | --- | --- |
| [Vítáme advent](https://www.stitina.cz/aktualne/kalendar-akci/vitame-advent-1636_167cs.html) | Štítina; Park, Hlavní, 74791 Štítina | 28. 11. | 15:00–20:00 | neuvedena; interval celého programu s rozsvěcením, nikoli potvrzená přesná hodina zapnutí stromu |
| [I. adventní koncert](https://www.praha16.eu/volny-cas/kalendar-akci/i-adventni-koncert-26167_706cs.html) | Praha-Radotín; Kulturně komunitní centrum Koruna | 29. 11. | 17:00, konec neuveden | neuvedena; Markéta Fassati, Pavel Větrovec a kapela |
| [Adventní Lanškroun](https://www.kclanskroun.cz/festival/adventni-lanskroun/) | Lanškroun; náměstí J. M. Marků | 29. 11.–20. 12. | obě hodiny neznámé | neuvedena; souhrnný krajní interval, ne potvrzení každodenního otevření |
| [Pekelné setkání s Mikulášem u SDH](https://www.praha16.eu/volny-cas/kalendar-akci/pekelne-setkani-s-mikulasem-u-sdh-26213_749cs.html) | Praha-Radotín; Hasičská zbrojnice, vlastní popis výslovně SDH Radotín | 5. 12. | 17:30, konec neuveden | neuvedena; veřejná pozvánka do zbrojnice, ne automaticky objednaná návštěva domácnosti |
| [II. adventní koncert](https://www.praha16.eu/volny-cas/kalendar-akci/ii-adventni-koncert-26168_707cs.html) | Praha-Radotín; Kulturně komunitní centrum Koruna | 6. 12. | 17:00, konec neuveden | neuvedena; Štěpán Rak, Ten vánoční čas |
| [III. adventní koncert](https://www.praha16.eu/volny-cas/kalendar-akci/iii-adventni-koncert-26169_708cs.html) | Praha-Radotín; Římskokatolický kostel sv. Petra a Pavla | 13. 12. | **15:00**, konec neuveden | neuvedena; autoritativní detail, nikoli přenesená hodina předchozích koncertů |

Další skutečně nalezené kandidáty se nepodařilo bezpečně přijmout: dvě radotínské filmové projekce 21. 11. v 17:00 a 20:00 mají obecné `Kino` mimo venue allowlist a podmínku nevhodnosti pro děti do 12 let; nepublikují se jako bezpodmínečně rodinná akce. Štítinský Mikuláš má pouze obecný údaj `Štítina`, bez konkrétního místa — zůstává review. Celková izolovaná fronta je 14 = původních 11 + tyto 3; projekce 14. 11. je známé vyřazení mimo sezonu, ne review. Neřeší se libovolným bodem uprostřed města.

## Geografická evidence

Nominatim dotazy byly provedeny sériově s cache a odstupem alespoň 1,1 s, s kontrolou ČR a správné obce/kraje. Původní odpovědi jsou v `private/`.

| Klíč | Doložený OSM objekt | Souřadnice / omezení |
| --- | --- | --- |
| Praha-Radotín | https://www.openstreetmap.org/relation/429567 | 49.9899078, 14.3635934; katastrální část Radotín v Praze, nikoli střed celé Prahy, přesný kostel nebo zbrojnice |
| Štítina | https://www.openstreetmap.org/relation/437618 | 49.9148086, 18.0125993; okres Opava, Moravskoslezský kraj |
| Lanškroun | https://www.openstreetmap.org/relation/440376 | 49.9124356, 16.6118541; okres Ústí nad Orlicí, Pardubický kraj |

## Ověření, snapshoty a bezpečnost

- Portable fixture testy byly doplněny před implementací: pozorováno nepodporované nové schema i chybějící registrace, následně GREEN. Lanškroun drží chybějící/obrácený/neplatný rok/interval, duplicity, přidaný JSON-LD, neznámé místo a nové cenové podmínky.
- Nezávislá Codex CLI statická review (bez dalšího Hermes agenta) odhalila dvě P2: dobrovolné/heading ceny obcházely guard a další numerický termín v označeném popisu se ignoroval. Všechny tři konkrétní mutace měly pozorovaný RED, opravy následně GREEN. Závěrečná re-review **PASSED**, exekuční testy jsou samostatný důkaz.
- Před pushem se main posunul na `2ce7937` (barevné mapové markery a legenda). Vlastní čistá větev byla znovu rebased, souběžné změny zachovány bez změny hashů zmrazeného collectoru/registru/geodat/testů/CI. Na této čerstvé základně prošlo **87 Python, 22 čistých JS a 33 Playwright testů**; custom-date-range, clear button, footer i barvy markerů zůstávají testované. Stejných 87 Python + 22 JS + public validace prošlo znovu v čisté přenosné kopii bez `private/`.
- Navíc skutečný historický snapshot (78) i rozšířená izolovaná projekce (113) vykresleny v desktopu 1440 px a mobilu 393 px: všechny čtyři kontroly ukázaly 14 krajů / 20 zdrojů bez JS výjimky. Nové obecní filtry vracejí 4 / 1 / 1 akcí. Vlastní datumy správně překrývají lanškrounský interval a za jeho koncem neukazují akci. Externí API a tiles blokované, není to test dostupnosti OSM.
- Stabilní offline replay po všech opravách: **113 akcí / 14 review / 22 vyřazení**, 0 HTTP, 0 AI, žádná chyba zdroje. Všech 107 baseline akcí shodných ve všech věcných polích mimo `verifiedAt`. Původních 78 se tím také zachovává.
- Read-only PR CI již obsahuje všechny aktuální main JS testovací soubory i čtyři browserové syntax checks; nebylo potřeba oslabovat nebo přepisovat workflow.
- Veřejné `events.json` a `review.json` jsou byte-for-byte beze změny. Jediný dodatek do coverage: 3 další explicitně nepublikované pending zdroje s 0 počty / null ověřením a regiony, původních 17 stavů i metriky zachovány. Safe public allowlist a validator nezměněny.
- Staré `final.sqlite` a výstupy `final-3` / `final-4` nebyly přepsány. Nové běhy používají samostatnou `wave2.sqlite`, kopii cache `wave2-http-cache` a vlastní výstupy. Žádný publisher, cron, konfigurace, infrastruktura, kalendář, produkční DB/cache ani UI se touto úlohou nemění. Žádní organizátoři nebyli kontaktováni.
- Po případném uživatelském merge je nutná bezpečná regenerace public trojice pod publisher lockem. Konflikty snapshotů řešit od aktuálního main, přidat jen chybějící pending položky, nikdy staré metriky nebo výzkumnou DB přes produkci. Tato úloha merge ani regeneraci/deploy neprovádí.
- Runtime odmítl i force push s přesným lease. Nebyla měněna konfigurace ani obcházeno schvalování. Po ověření, že vzdálený tip `a9e4737` obsahuje výhradně již rebasovanou vlastní práci, byl jen uvnitř vlastní feature větve přidán synchronizační ancestry merge commit se stejným tree SHA před/po; následoval běžný fast-forward push. Žádná změna souborů tímto krokem, žádný přepis vzdálené historie a žádné sloučení PR/main.

## Finální síťová měření

Dvě skutečné finální kontroly po všech opravách, statické re-review a stabilním offline replay úspěšně dokončeny 12. 11. 2026. Jediný runner `proc_f95abe4769b2` / PID 1294084 skončil kódem 0; nebyl spuštěn duplicitní sběr. Výstupy byly samostatně znovu validovány.

| Kontrola | Začátek CET | Celkový čas včetně validace | Vnitřní čas collectoru | HTTP / 304 | Nové / změněné / nezměněné | Akce / review / vyřazení | Chyby zdrojů |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | 19:18:49 | **7 min 27 s** (446,603 s) | 443,103 s | 205 / 12 | 6 / 0 / 107 | 113 / 14 / 22 | 0 |
| B | 19:26:16 | **7 min 18 s** (437,825 s) | 431,769 s | 205 / 13 | 0 / 0 / 113 | 113 / 14 / 22 | 0 |

Oba běhy mají 0 AI volání a skutečnou síť s robots/per-host limity a podmíněnou cache, nikoli fixtures. Všech 107 předchozích akcí i původních 78 porovnáno po všech věcných polích, mimo pouze `verifiedAt`; nic se nezměnilo. Všech 113 věcných záznamů je shodných mezi finálními běhy. Čistý přírůstek **6 této dávky / 35 celého PR** je programový rozdíl ID, nikoli domněnka z počtu insertů opakovaného běhu. Všech šest nových detailů má řádky provenance pro všech devět evidovaných věcných polí, přesnou primární URL a hash zachyceného obsahu; auditní tabulka obsahuje přesně jejich URL množinu.

Timeout collectoru zůstává **600 s**, read-only ověřený efektivní scheduler timeout **3600 s**. Oba skutečné běhy prošly nezměněným limitem, není tedy runtime blocker pro tuto dávku; nejde o garanci pro další zdroje nebo budoucí výpadky. Zmrazené hashe implementace, registru, geodat, nových testů a PR CI po obou bězích souhlasí. Rebase na čerstvý main a synchronizace historie je nezměnily. Po této dvojici se doplňuje pouze dokumentace a PR, žádná další implementace ani sběr.

## Zbývající mezery

Zastoupení všech krajů není pokrytí všech krajů. Praha mimo tři vybraná radotínská místa je prakticky mezerou. Pardubice a Ostrava stále nemají integrovaný městský zdroj; Lanškroun má jen jeden souhrnný interval, Štítina jen jeden místní program. Ostatní městské a oblastní mezery a robots/TLS blokace první dávky zůstávají platné. Další implementace nebyla na konci rozpočtu zahájena.
