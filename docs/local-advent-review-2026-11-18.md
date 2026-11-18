# Místní adventní redakční revize — 18. listopadu 2026

## Rozsah návrhu

Výchozí verze je `df70aeef448a6e090293771fc22c03e6ff703ffe` (`origin/main`). Jde pouze o izolovaný návrh: žádný push, sloučení ani nasazení; žádné změny produkční databáze, plánovače, kalendářů nebo pozvánek.

- `data/reviewed-events.json`: 172 → 186 záznamů; 14 nových, tři doložené opravy, žádné odstranění. Všech 169 nedotčených záznamů je shodných včetně původního `verifiedAt`.
- Zachovány kanonické identity, primární URL a vlastníci všech původních záznamů. Doplňující podklady patří do poznámek, nikoli do migrace primárního zdroje.
- Čtyři nové vazby jsou omezené na přesné dokumenty/stránky PDF a schválené obce. Žádný existující zdroj ani ochrana soukromí se nemění. Nové záznamy mají polohu `null`.
- `site/events.json` a `site/review.json` zůstávají bajtově shodné s výchozí verzí. `site/coverage.json` pouze přidává čtyři čekající zdroje s nulovými počty a bez časů kontroly; staré zdroje i celkové metriky zůstávají shodné. Registrace není dokladem nasazení nových akcí.
- Nové `generatedAt` označuje revizi feedu. Jednotlivé `verifiedAt` vycházejí z konkrétních ověření, nikoli z času přenosu.

## Nové kanonické záznamy

Veřejné primární podklady: [Říčanský kurýr, listopad 2026](https://www.maks-ricany.cz/prilohyarchiv/11963/kuryr-2026-11.pdf), [Senohrabská hláska, listopad 2026](https://www.senohraby.cz/modules/file_storage/download.php?file=c06d18de%7C764), [program Rybovek](https://www.rybovky.cz/2026/11/08/terminy-2026/), [koncert Mukařov](https://www.mukarov.cz/zivot-v-obci/akce-obce/adventni-koncert-spiritual-kvartet-2026) a [pozvánka Louňovice](https://www.lounovice.cz/aktuality/aktuality-1/pozvanka-na-adventni-akce-978cs.html).

| ID | Obec / program | Datum a začátek | Primární podklad |
| --- | --- | --- | --- |
| `e-39b9abf0c13d1c73` | Mukařov — Spiritual Kvartet | 13.12. 19:00 | obecní detail a plakát; pořadatelem odkazovaný GoOut 390 Kč |
| `e-096c02c02a7bdfba` | Říčany — vánoční setkání seniorů | 23.11. 14:00–17:00 | Kurýr s.14; zdarma, omezené zaměření |
| `e-110e5d971533b042` | Senohraby — rozsvícení stromu | 28.11. 16:30 | Hláska s.1; světýlková stezka zvlášť od 16:00 |
| `e-a5e935841c99d16d` | Senohraby — začátek adventu v kapli | 28.11., navečer | Hláska s.12; přesná hodina neznámá |
| `e-6a8e66c63a4c2026` | Říčany — slavnostní bohoslužba | 29.11. 09:30 | Kurýr s.62; Stará radnice |
| `e-cb79abeaa78ab473` | Říčany — první adventní neděle a strom | 29.11. 17:00 | Kurýr s.17; Masarykovo náměstí |
| `e-df813aac82c7766c` | Říčany — Slunečnice a vánoční tvoření | 2.12. 16:00 | Kurýr s.12; obecní přehled místa |
| `e-ff24dadea4bc2683` | Říčany — druhá adventní neděle | 6.12. 17:00 | Kurýr s.17 |
| `e-eddd36503c947eb5` | Říčany — Česko zpívá koledy | 9.12. 18:00 | Kurýr s.17 |
| `e-c613e8bf00e51511` | Říčany — třetí adventní neděle, jarmark | 13.12. 14:00 | Kurýr s.17 |
| `e-49b64568725cca48` | Ondřejov — Rybova mše vánoční, koncert | 19.12. 18:00 | přesný program pořadatele; vstup nejdříve 30 minut před začátkem |
| `e-d24f8b70955c6bad` | Říčany — čtvrtá adventní neděle | 20.12. 17:00 | Kurýr s.17 |
| `e-782a8431a6aa8106` | Říčany — České Vánoce | 23.12. 17:00 | Kurýr s.16; Betlémské světlo jako součást programu, bez samostatné hodiny |
| `e-9bde7f6532006ae0` | Louňovice — vánoční setkání a strom | 29.11. od 14:00, strom 17:00 | obecní článek a oba připojené plakáty |

Louňovice tvoří jeden společný program, nikoli dvě duplicitní akce. Článek označuje místo rozsvícení Kamenický skanzen, druhý plakát Horní náves; rozpor zůstává v místě i poznámce, bez souřadnic. Plakáty nemají vytištěný rok; rok 2026 pochází z aktuální obecní pozvánky zveřejněné 18.11.2026, nikoli z názvu souboru. [Plakát setkání](https://www.lounovice.cz/evt_image.php?img=1667&v=1794995208), [plakát rozsvícení](https://www.lounovice.cz/evt_image.php?img=1668&v=1794995226).

Celý katalog 2 775 akcí byl porovnán podle URL, data, skutečné obce a programu, ne pouze podle nového identifikátoru. Říčanský koncert Richarda Pachmana ve stejný den jako zpívání koled má jiné místo, hodinu a program; nejde o duplicitu. Prvních třináct nových ID zachovává dosavadní deterministický recept z výzkumní identity, bez zveřejnění této identity. ID nové Louňovické akce je `e-` + prvních 16 znaků SHA-256 řetězce `reviewed|<primární URL>|2026-11-29|Louňovice`.

## Opravy existujících akcí

| Zachované ID | Změna | Zachovaný primární vlastník |
| --- | --- | --- |
| `e-2a25cd0b98ed6aba` | Věnce RC Lodička: 18.11. ověřeno 6 volných z 15 míst, přinést chvojí, děti s pomocí rodičů. Starší snímek osmi míst není aktuální stav. Cena, datum, hodiny, místo a souřadnice beze změny. | `reviewed-lodicka-webooker-eu` |
| `e-4f15af21f62bd966` | Kunice: vystoupí děti MŠ a ZŠ, hrnečky s sebou; doplněn primární plakát. Datum, hodina, původní místo i souřadnice beze změny. | `reviewed-www-kunice-cz` |
| `e-d01bbc0c574b613c` | Muzeum Říčany: při dvou kontrolách 18.11. e-shop uvádí poslední jedno místo místo dvou. Primární muzeální detail zůstává; e-shop je doplňující podklad a registrační URL. Datum, hodiny, cena a poloha beze změny. | `reviewed-muzeumricany-cz` |

Kapacity jsou označené jako časové snímky, nikoli záruka budoucí dostupnosti; žádná rezervace neproběhla. U tří oprav se mění pouze popis, poznámky, příslušný registrační text a doložené datum ověření; žádné další pole.

## Vyřazené a nejisté podklady

- Říčanská výstava s koncem 3.1.2027 zůstává mimo tento návrh. Není převlečená za jednodenní výstavu ani přejmenovaná na nedoloženou vernisáž.
- Mnichovická půlnoční mše označená jako 24.12. ve 24:00 skutečně začíná 25.12. a zůstává mimo sezonní hranici. Není vydávaná za 24.12. v 00:00 ani za program s neznámou hodinou.
- Senohrabská kaple zůstává bez hodin; 18:00 na téže stránce patří Červené středě 25.11., nikoli adventu 28.11.

## Provedené kontroly

- Nejprve selhaly nové faktické testy kvůli chybějícím akcím/vazbám a původnímu kapacitnímu snímku; po úpravě procházejí.
- `python3 -m unittest discover -s tests -v`: **294 testů prošlo**; čistý izolovaný worktree bez produkčního `private/`.
- Samostatné zaměřené sady: šest nových faktických testů, 22 lifecycle/feed testů a čtyři testy obecních registrací prošly.
- `node --test tests-ui/helpers.test.mjs tests-ui/pilot.test.mjs tests-ui/feedback.test.mjs`: **33 testů prošlo**.
- `python3 scripts/validate_public.py site`: platná výchozí projekce **2 775 akcí**, včetně nových čekajících registrací.
- Dva průchody skutečným sběračem a validátorem s plným registrem a izolovanou zálohou synchronizované SQLite: **2 789 akcí**, **14 přidáno**, **3 opraveny**, **0 odstraněno**, **2 772 kompletních původních payloadů i dat ověření zachováno**. Druhý průchod: žádná další nová ani změněná akce. Všechny původní DB identity/vlastníci a nadbytečný nepoužitý řádek zůstávají zachované; 1 012 neredakčních stavů zdrojů a jejich původní evidence beze změny. Fronta nadále obsahuje 592 kandidátů.

Tyto dva průchody jsou **offline zkouškou přenosu přesných místních bajtů**, nikoli skutečným HTTP přenosem ze zveřejněné SHA-pinned URL. Nenahrazují schválení změny, následné dva veřejné přenosy téže zmrazené revize a kontrolu nasazených dat pod publikačním zámkem. Tyto kroky zůstávají před publikací neprovedené; návrh nemá technický integrační blokátor.
