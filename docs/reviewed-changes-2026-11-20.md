# Dvě ověřené redakční změny — 20. listopadu 2026

Rozsah: nový charitativní koncert na zámku Berchtold a doplnění programu již
publikovaného Struhařovského pekla. Nejde o celostátní crawl ani o důkaz nového
zveřejnění pořadatelem. Osobní kalendář, pozvánky a výzkumný deník se nemění.

## Primární ověření

Oba detaily i jejich skutečné plakáty byly nezávisle znovu načteny HTTP 200
20. listopadu 2026 a plakáty vizuálně přečteny.

- **Berchtold**, `e-0e0e431b8c528740`: [pořadatelský kalendář](https://zamekberchtold.cz/aktuality/kalendar-akci/)
  potvrzuje 12. prosince 2026 **15:30–17:00**, Červený sál, dobrovolné vstupné
  na Děti dětem a nutnost předem e-mailem ohlásit počet diváků.
  [Oficiálně vložený plakát](https://i0.wp.com/zamekberchtold.cz/wp-content/uploads/2026/11/12.12.26.png?resize=1000%2C472&ssl=1)
  potvrzuje Hlavní 6, Kunice–Vidovice. Poslední hudební bod končí 16:50;
  to nepřepisuje pořadatelem výslovně uvedený konec celé akce v 17:00.
  Claireton Chorale, String Ladies, předání daru a podpis rytířů jsou zachovány.
  Veřejná pozvánka zahrnuje rodiny; nejde o pobytový balíček.
  Souřadnice zůstávají `null`. Kapacita a potvrzení účasti nejsou ověřeny.
- **Struhařov**, `e-683c7a9a1c1174a4`: [původní obecní detail](https://www.struharov.cz/zivot-v-obci/kalendar-akci/struharovske-peklo-u-frantiska-835_214cs.html)
  potvrzuje 5. prosince 2026 v 17:30 a hřiště u Františka u Hliněného rybníka.
  [Z detailu odkazovaný plakát](https://www.struharov.cz/evt_image.php?img=5099&v=1795014611)
  výslovně uvádí dětský program s nadílkou, Mikuláše na závěr a výzvu přijít
  včas. Nahrazuje se pouze dřívější tvrzení, že tyto skutečnosti nejsou známy.
  Existující ID, vlastník `reviewed-www-struharov-cz`, primární URL, místo,
  datum, hodina a neznámá cena/registrace/konec zůstávají beze změny.

## Identita a registrace

Porovnány všechny aktuální veřejné události podle URL, data, obce, místa,
názvu a programu. Koncert Berchtold není již publikovaný koncert Sylvy
Čmugrové a Ladislava Horáka 5. prosince (`e-9fc560d009441d49`).
Nový koncert je nový pro katalog; datum prvního zveřejnění nebylo zjištěno.

Přidává se jediný zdroj `reviewed-berchtold-charity-2026`: právě jedna přesná
URL pořadatelského kalendáře, právě Kunice–Vidovice / Středočeský kraj,
žádné povolené souřadnice. Ostatní zdrojové definice se nemění. Regresní test
zkouší celý registr, jiné hostitele/cesty/query/fragmenty/obce/kraj i domyšlené
souřadnice. Kontaktní adresa ani telefon se do veřejných dat nekopírují.

## Publikační hranice

Vstupem je čerstvá kopie odpovídající produkční SQLite pod existujícím zámkem,
po ověření přesného nasazení výchozího commitu a všech tří JSON. Produkční
SQLite se při této přípravě pouze čte; nepřepisuje se ani nepřipravuje napřed.
Výstup musí vytvořit nezměněný sběrač z veřejného SHA-pinned feedu dvakrát
pod celým registrem. Do stejného PR patří feed, přesná registrace, testy a
všechny tři sběračem vytvořené veřejné projekce.

PR samo není souhlas ke sloučení či publikaci. Až po schváleném sloučení a
ověření přesného nasazení lze pod zámkem použít nativní preflight a následně
publisher `--reviewed-only`; nikdy před nasazením schváleného PR.

## Provedené integrační ověření

- Výchozí commit `4d6d2016fde3c848c528647bab98c7c7e9e49411`: nativní
  ověření úspěšného Pages workflow a přesná shoda všech tří nasazených JSON.
  Produkční SQLite otevřena read-only pod `publish.lock`; úplná projekce
  všech 2 865 akcí a multiset všech 897 kandidátů přesně odpovídaly publikaci.
  Pending publikační stav nebyl přítomen. Nebyla nutná změna produkční DB.
- Zmrazený veřejný feed z feature větve:
  `https://raw.githubusercontent.com/romanzdk/advent-cesko-pilot/1ae1217e3b5a6175d449925e2efd1b5897452ac9/data/reviewed-events.json`
  (SHA-256 `1960700bbcdbb788532aa4f30f65f1607ad1c3515bb1471a79fe18fd425ec7b7`).
  Obsahuje 191 záznamů proti původním 190.
- Dva závěrečné skutečné cykly pod celým registrem **1 074 zdrojů**
  (původně 1 073), z toho 62 redakčních (původně 61). Každý cyklus používá
  nezměněný CLI sběrač `--reviewed-only --source-id` jednou pro Berchtold a
  jednou pro stávajícího struhařovského vlastníka. Ostatní zdroje se nečtou.
  Oddělené čerstvé HTTP cache doložily **HTTP 200 těla feedu v obou cyklech**;
  druhý zdroj v každém cyklu provedl skutečnou podmíněnou kontrolu HTTP 304.
  Starší předběžné průchody se společnou cache jsou zachovány samostatně.
- Obě úplné výsledné projekce souhlasí: **2 866 akcí, 897 kandidátů**.
  Přidáno přesně `e-0e0e431b8c528740`, změněno přesně
  `e-683c7a9a1c1174a4` pouze v `description`, `notes`, `verifiedAt`,
  odstraněno **0 ID**. Zbývajících **2 864** původních akcí má beze změny
  všechna pole včetně původního `verifiedAt`.
- Zachován úplný multiset kontrolní fronty, všechny nedotčené definice a
  stavy zdrojů, vlastnictví i původní soukromá provenance. Oba dotčené zdroje
  mají `status: ok`, `lastError: null` a aktuální `lastSuccess`; Berchtold
  má jednu akci, stávající Struhařov tři. Kontrola přenosu není nové ověření
  těchto dvou dalších struhařovských akcí.
- Veřejný validátor přijal oba výstupy. Časy 11,348 s a 16,456 s zahrnují
  sběr, validaci a kontroly zachování; nejde o dobu celostátního crawlu.
  Všechny tři veřejné JSON pocházejí beze změny z druhého cyklu. Souhrnné
  metriky v coverage popisují poslední cílený průchod, ne celý uložený katalog.
- Nové čtyři regresní testy projdou; na výchozích datech tři z nich správně
  selžou. Dřívější test požadující neznámou nadílku byl úzce aktualizován na
  nyní doložený plakát; striktní pojistky a implementace zůstaly nezměněny.
- Celá sada **302 Python testů** prošla v čisté přenositelné kopii bez
  adresáře `private/` (219,987 s včetně spuštění). Dále prošlo **33 čistých
  JavaScript testů**, veřejný validátor pro 2 866 akcí, syntaktické kontroly
  čtyř browser modulů a místní publisher `--check --reviewed-only`.
  Poslední volba je pouze kontrolou připravenosti, nikoli publikací.
