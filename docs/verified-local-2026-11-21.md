# Ověření místních adventních doplnění — 21. listopadu 2026

Tento podklad popisuje návrh změny veřejných dat, ne její nasazení. Kalendáře, pozvánky, rezervace, produkční databáze, webové rozhraní a plánovače nebyly měněny.

## Přesný obsahový rozdíl

### Přidané akce

| Veřejné ID | Místo a ověřený termín | Podmínky a meze podkladu |
|---|---|---|
| `e-b1af12e0a050d855` | Mikulášská stezka, Přestavlky u Čerčan, zahájení 22.11.2026 | „Po celý týden“; doslovný konec, denní hodiny, trasa a přesné místo nejsou zveřejněny. `endDate`, oba časy a poloha zůstávají `null`; datum není tvrzením jednodenní akce.[1] |
| `e-05a4eaf823581eb1` | Adventní setkání s Mikulášem, Přestavlky u Čerčan, 28.11.2026 od 16:00 | Strom, koledy, Mikuláš s čertem a andělem, dílničky a perníčky; přesné místo, konec a hodina vlastního rozsvícení nejsou uvedeny.[1] |
| `e-510740de107f7398` | Rozsvícení Vánočního stromku, Lštění, 28.11.2026 16:00–19:00, zahrada obecního úřadu | Vlastní rozsvícení v 17:00, občerstvení a prodej dárků od 16:00.[2] |
| `e-bb4c321bbaaa07b6` | Rozsvícení stromečku na Borovce, Borová Lhota (Pyšely), 28.11.2026 od 16:30 | Primární bulletin infocentra města Pyšely přetištěný obcí Mirošovice. Bez domyšleného vstupného, adresy domu, konce či souřadnic.[3] |
| `e-12735559062e1155` | XXII. adventní koncert, Lštění, 29.11.2026 14:00–16:00, kostel sv. Klimenta na Hradišti | FAMIREDO a žáci ZUŠ s hosty; vstupné dobrovolné. Pořadatel nabízí rezervace, jejich povinnost ani aktuální kapacita nejsou potvrzeny. Konec 16:00 je údaj obecního kalendáře, plakát potvrzuje začátek.[4] |
| `e-3993e134c57ca543` | Vánoční BESSÍDKA se skupinou BESSONI, Čerčany, 5.12.2026 od 20:00, kulturní dům | Vchod přes pizzerii, večerní besídka a tanec; „Možná přijde Mikuláš“ není záruka Mikulášovy účasti nebo nadílky. Konec, cena a registrace nejsou zveřejněny.[5] |
| `e-78a9eb4f782e55f5` | Kostelecké trhy adventní, Kostelec nad Černými lesy, 12.12.2026 09:00–16:00, Náměstí Smiřických | Originální plakát pořadatele potvrzuje sobotu, farmářské a řemeslné produkty, občerstvení a doprovodný program; vstupné ani povinnost rezervace návštěvníků nejsou uvedeny.[11] Plakát je zveřejněn na domovské stránce pořadatele.[10] |

Všech sedm nových záznamů má `location: null`. Nebyly doplněny odhadnuté souřadnice ani kontaktní údaje. Sedmá akce je doplnění původního návrhu PR70; všech 197 dřívějších redakčních payloadů včetně jejich `verifiedAt` zůstalo přesně zachováno.

### Opravené stávající akce

- `e-c03f5e83a5330fbf`: Chocerady, 28.11.2026, začátek 16:00 zachován, konec doplněn na 19:00. Vlastní rozsvícení 17:00, doprovodný program a orientační charakter časů doplněny do popisu a poznámek. Původní primární URL, vlastník `reviewed-www-chocerady-cz` a poloha zůstaly zachovány; nový program PDF a plakát jsou pouze doplňující podklady.[6]
- `e-aacd4dfa028ba519431c`: Vánoční tržiště pro hospic, Čerčany, 29.11.2026, začátek 13:00 zachován, konec doplněn na 18:00 a místo na „Kulturní dům, Sokolská 28, Čerčany“ podle plakátu pořadatele.[7] Vedlejší bulletin uvádí konec 16:00; rozpor zůstává výslovně v poznámkách.[3] Existující údaj `0 Kč` z Posázaví nebyl změněn na nové tvrzení pořadatele; jeho odlišný původ je uveden v poznámce.[9] Zachováno ID, primární URL, poloha a živý vlastník `cercany-posazavi-calendar`; nejde o novou kopii v redakčním feedu.
- `e-2a25cd0b98ed6aba`: Adventní věnce, Všechromy, 25.11.2026 17:00–19:00; veřejná registrace Webooker 50457 měla při kontrole 21.11.2026 v 08:32:42 UTC čtyři volná místa z patnácti místo předchozích šesti. Jde o pomíjivou dostupnost, ne rezervaci nebo změnu termínu; ostatní podmínky a poloha se neměnily.[8]

Žádné veřejné ID nebylo odstraněno. `e-d029b91f5b99098da4b9` (Slavnosti dobra a radosti, Čerčany) má pouze nové `verifiedAt` ze skutečné opakované kontroly stejného živého zdroje; ostatní jeho pole jsou přesně shodná.

## Vlastnictví a trvalý přenos

- Kanonický plný `data/reviewed-events.json` má 198 záznamů: všech 191 původních redakčně vlastněných veřejných akcí a sedm nových. Pouze dvě původní redakční akce mají změněné skutečnosti a datum ověření; původní `verifiedAt` ostatních zůstalo zachováno.
- Čtyři nové redakční skupiny mají přesné seznamy schválených URL, hostitele, obec, kraj a pouze prázdné seznamy schválených souřadnic. Lštění a Čerčany sdílejí hostitele, nikoli primární URL.
- Kostelecký trh nemá v celém původním katalogu shodu podle obce, primární URL, náměstí ani programu. Již existující, dosud neobsazený vlastník `reviewed-centrum-pecka-cz` byl zachován a zúžen na jedinou přesnou URL plakátu, původní obec a kraj; jeho schválené souřadnice jsou nyní prázdné. Nevznikl duplicitní zdroj ani překryv s nesouvisejícím městysem Pecka. Domovská stránka zůstává jen doplňujícím podkladem.[10][11]
- Přesná dosud nepoužitá URL bulletinu pro Borovou Lhotu byla vyčleněna z obecné redakční skupiny Mirošovic. Žádná již zveřejněná akce této skupiny nemění vlastníka; jiným URL se nerozšiřuje povolení k cizí obci.
- Oprava tržiště je `event_reviews` původního živého vlastníka, vázaná na přesnou URL, zdrojovou obec/ID, nadpis, datum, konec intervalu, původní místo a obsahový hash. Doplněná úzká podpora otisku Posázaví váže celé jediné JSON-LD Event včetně míst, nabídek a obrazových URL plus skutečný nadpis. Změna podkladu vrací položku do kontroly; obecné kontroly, vlastnictví a limity sběru se nemění.

## Dva skutečné závěrečné průchody

Výchozí `origin/main`: `e79a01e90839d7292c6ee2202b06cca3a8c81d44`. Před prací byla pod existujícím publikačním zámkem pořízena read-only SQLite backup API kopie, nikoli kopie souboru běžící databáze. Projekce této izolované kopie přes skutečný sběrač se přesně shodovala s celými veřejnými payloady 2 885 akcí, 1 074 stavů zdrojů a multisetu 976 kontrolních kandidátů. Všechny tři skutečné JSON na `kamnaadvent.cz` byly znovu porovnány bajtově s výchozím main před zahrnutím návrhu projekcí.

Zmrazený veřejný přenos:

```text
https://raw.githubusercontent.com/romanzdk/advent-cesko-pilot/297176cad5ce1a1880e820fb4ca08fd680b3afdf/data/reviewed-events.json
SHA-256 b246ecab9af3054b7700f43b10b9523dfbafce3a35b7030e143319f212a14a8e
213566 bytes
HTTP 200 at 2026-11-21T09:06:59.222158+00:00
HTTP 200 at 2026-11-21T09:07:12.245368+00:00
```

Každý průchod měl novou izolovanou HTTP cache, skutečné načtení tohoto těla a plný registr. Stejné ověřené tělo bylo v rámci průchodu znovu použito v paměti pro jednotlivé cílené redakční vlastníky, nikoli nahrazeno lokální fixture. Síťový rozsah tvořilo sedm dotčených redakčních vlastníků včetně `reviewed-centrum-pecka-cz` a pouze živý zdroj `cercany-posazavi-calendar`, ten byl načten skutečně v obou průchodech. Nejde o nový celostátní crawl.

Oba výsledky mají 2 892 akcí, 1 078 registrovaných zdrojů, stejných sedm přidaných a tři významově opravená ID, žádná odebraná ID a přesně původní multiset 976 kontrolních kandidátů. U všech 1 070 nedotčených původních zdrojů jsou stavy přesně shodné; vlastníci všech původních databázových akcí jsou zachováni. Z původních 2 885 akcí je 2 881 celých payloadů přesně shodných; tři mají výše popsané opravy a jedna pouze skutečně obnovené datum ověření. Oba závěrečné katalogy jsou významově shodné po vyloučení `verifiedAt` dvou živě znovu načtených čerčanských akcí. Všechny ostatní časové údaje ověření jsou mezi průchody přesně shodné.

Původní důkaz PR70 nebyl přepsán: dva předchozí skutečné přenosy revize `6d42c7e62dea2366d416820e042b6cfe5ffc493b` měly SHA-256 `7a66c2bd9b8459c9ab8c7b6a0f0d46e47854f5167d8245472636a3284856378e`, 212549 bajtů a HTTP 200 v 08:46:30 a 08:46:42 UTC. Rozšířené průchody navázaly na tutéž izolovanou `validated.sqlite` po read-only SQLite backup API záloze před doplněním. Oproti předchozímu katalogu PR70 přibyla právě jedna akce; žádný předchozí fakt se nezměnil, pouze dvě skutečně znovu načtené čerčanské akce dostaly nové `verifiedAt`.

V PR jsou zahrnuté všechny tři sběračem vytvořené projekce z druhého průchodu; samostatně změněný bootstrap bez odpovídajících projekcí by neprošel bezpečným převzetím publikovaného stavu. Po případném schváleném merge patří nasazení, ověření kanonických main bajtů a nativní převzetí stavu pod publikačním zámkem do samostatného oprávnění. Izolovaná databáze není produkční stav a nesmí se přepsat do produkce bez jejího nového úplného porovnání.

## Kontroly

- `python3 -m unittest discover -s tests -v`: 309 testů, úspěch; stejných 309 testů prošlo také v čisté zdrojové kopii bez adresáře `private/`.
- `node --test tests-ui/helpers.test.mjs tests-ui/pilot.test.mjs tests-ui/feedback.test.mjs`: 33 testů, úspěch.
- `python3 scripts/validate_public.py site`: 2 892 validních akcí.
- `python3 scripts/publish_daily.py --check`: úspěch, pouze místní modulový preflight, nikoli publikace.
- Nové přenositelné regresní testy ověřují přesné nové vazby a odmítnutí cizích hostitelů/URL/obcí/krajů/souřadnic, neznámý konec stezky, odlišení programu a rozsvícení, podmínky koncertu, nestálou kapacitu i reálné dočasné SQLite stažení změněného Posázaví podkladu do kontroly.

## Sources

[1] https://www.prestavlkyucercan.cz/zivot-v-obci/kalendar-akci/adventni-setkani-s-mikulasem-1996_417cs.html
[2] https://www.lsteni-zlenice.cz/zivot-v-obci/kalendar-akci/rozsviceni-vanocniho-stromku-401_149cs.html
[3] https://www.mirosovice.cz/cs/obec/aktuality/kulturni-a-sportovni-akce-v-pyselich-a-okoli-1247cs.html
[4] https://www.lsteni-zlenice.cz/zivot-v-obci/kalendar-akci/xxii-adventni-koncert-344_131cs.html
[5] https://www.lsteni-zlenice.cz/zivot-v-obci/kalendar-akci/vanocni-bessidka-se-skupinou-bessoni-474_172cs.html
[6] https://www.chocerady.cz/evt_file.php?file=5598&original=PROGRAM%20ROZSV%C3%8DCEN%C3%8D%20V%C3%81NO%C4%8CN%C3%8DHO%20STROMU%20CHOCERADY%202026.pdf
[7] https://tri-cercany.cz/wp-content/uploads/2026/10/trziste.png
[8] https://lodicka.webooker.eu/graphql
[9] https://tourist.posazavi.com/cz/kalendar-akci/46727-vanocni-trziste-ve-prospech-hospic-dobreho-pastyre.html
[10] https://centrum-pecka.cz
[11] https://centrum-pecka.cz/wp-content/uploads/2026_VANOCE_fb-1024x577.jpg
