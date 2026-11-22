# Ověřené místní doplnění — 22. listopadu 2026

## Rozsah dat

Výchozí katalog obsahoval 2 912 akcí. Nová projekce obsahuje 2 919 akcí: sedm nových termínů, šest doložených oprav, žádné odstraněné ID. Z ostatních původních záznamů je 2 898 zachováno úplně; osm sourozeneckých záznamů dotčených živých zdrojů má změněný pouze `verifiedAt`. Všech 999 kandidátů ke kontrole je zachováno jako multiset, stejně jako všech 1 072 nedotčených stavů zdrojů. Registr má nově 1 082 zdrojů místo 1 078. Výběr nadále není úplným katalogem akcí.

## Nové termíny

- Čerčany, 28.11. 10:30–12:30: tvoření adventních věnců. [Veřejný rozvrh pořadatele Webooker](https://todelamja.webooker.eu/flutter/#/events), událost 51556, potvrzuje rok i interval; [plakát](https://tri-cercany.cz/wp-content/uploads/2026/11/Adventni-vence_2026_plakat-1.jpeg) místo a cenové varianty. Nepřebírá se proměnlivá kapacita.
- Čerčany, 29.11. od 15:00: venkovní rozsvěcení před kulturním domem podle [obecního plakátu](https://static.posazavi.com/Pictures/RelatedEventImages/2026/10/26/40146.jpeg). Odlišeno od již evidovaného hospicového tržiště 13:00–18:00; hodina vlastního rozsvícení neznámá.
- Kostelec nad Černými lesy, 19.12.: Carmina Bohemica v zámecké kapli sv. Vojtěcha podle [ročního kalendáře pořadatele](https://zamekkostelec.cz/kalendar-akci-na-rok-2026/). Hodina zůstává neznámá.
- Lštění, 24.12.: Betlémské světlo / zpívání koled podle [ročního plánu kostela](https://www.lsteni-zlenice.cz/evt_file.php?file=2294). Vedlejší údaj 14:00–17:00 označuje otevření kostela, nikoli potvrzené hodiny programu.
- Pyšely, 6., 13. a 20.12. od 16:00: tři jednotlivá otevření neprodejní vánoční výstavy v infocentru a knihovně, Náměstí T. G. Masaryka 4, vstup zdarma. [Plakát](https://static.posazavi.com/Pictures/RelatedEventImages/2026/11/3/40293.png) doplňuje [datovaný městský detail](https://tourist.posazavi.com/cz/kalendar-akci/46827-vanocni-vystava.html). Původní termín 29.11. si ponechává své ID a živého vlastníka. Nejde o nepřetržitý interval ani o výstavu Galerie u Marie.

Nové termíny mají neznámé souřadnice. Přesné redakční vazby na nové podklady nepřekrývají živé obecní HTML detaily.

## Opravy při zachované identitě

- Borová Lhota: setkání od 15:00 na návsi u kapličky; vlastní rozsvícení 16:30. Zachována původní hlavní URL, nové plakáty jsou doplňujícími podklady.
- Kovářovice: náves v Kovářovicích, nikoli pyšelské náměstí. Přesné mapování místní části, souřadnice `null`, původní živý vlastník a ID.
- LOKall Čerčany: konec 15:00 a adresa Sokolská 584 podle plakátu pořadatele.
- Pyšelská výstava 29.11.: přesná adresa, vstup zdarma, neutrální kategorie místo trhů.
- LOŠBATES 30.11.: školní kalendář uvádí 16:00–19:00, plakáty 17:00. Datum zůstává, oba strojové časy jsou `null`; poznámka zachovává rozpor, netvrdí přesun.
- PANCHARTI: odstraněna nepodložená seniorská podmínka; nezavádí se jiné věkové omezení. Známý rozpor dne v týdnu zůstává výslovný.

## Ověření přenosu a zachování katalogu

Dva závěrečné skutečné průchody použily plný registr a dvě nezávislé kopie odpovídající produkční SQLite. Každý měl vlastní prázdnou HTTP cache. Feed byl načten z [neměnné revize `714d25984852f1f06ec5ac6af7a4e52bfbfa07c5`](https://raw.githubusercontent.com/romanzdk/advent-cesko-pilot/714d25984852f1f06ec5ac6af7a4e52bfbfa07c5/data/reviewed-events.json): oba první přenosy byly HTTP 200, po 222 115 bajtech, SHA-256 `4e5435d7f83204ae41918d622ae1158f26b2bc3e9327b6933f0813d83194072d`. Sedm dalších přenosů téhož feedu v každém průchodu bylo HTTP 304, nikoli dalších sedm přenosů těla.

Síťový rozsah: osm dotčených redakčních vlastníků a pouze dva dotčené živé zdroje, Pyšely a Čerčany. Neproběhl celostátní crawl. Oba úplné výstupy prošly veřejným validátorem a sémanticky se shodují. Doby průchodů včetně validace byly přibližně 35,8 a 68,1 sekundy. Pyšely si ponechávají původní stav `partial` s jedním existujícím kandidátem; nevznikla nová chyba zdroje.

Přenos aktualizuje jen svůj stav; není novým ověřením všech původních primárních stránek. Nedotčené redakční `verifiedAt` se nemění. Projekce `events`, `coverage` i `review` pocházejí ze sběrače, nejsou ručně slepené.

Izolovaná zkouška nativního převzetí publikace vložila sedm akcí a aktualizovala čtrnáct původních řádků (šest oprav a osm nových časů ověření); opakování změnilo nula akcí. Součástí opravy je úzké sjednocení validátoru a nativního převzetí pro přesně mapovanou místní část a obsahově vázanou opravu původního místa. Striktní vlastnictví, bootstrap a časové pojistky zůstávají zapnuté.

Publikace po schválení vyžaduje standardní ověření přesného nasazení, shody kanonického feedu a všech tří JSON a nativní převzetí pod publikačním zámkem. Samotný test větve není nasazení ani oprávnění ke sloučení.
