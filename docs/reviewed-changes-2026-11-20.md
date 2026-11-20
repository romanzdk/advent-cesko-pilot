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
