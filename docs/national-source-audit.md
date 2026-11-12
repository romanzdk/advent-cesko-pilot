# Celostátní průzkum primárních zdrojů — 12. listopadu 2026

Tento dokument uchovává výsledky **první dávky** (17 zdrojů / 11 krajů, 107 izolovaných akcí). Navazující [druhá dávka](national-wave2-audit.md) přidává Radotín, Lanškroun a Štítinu: registr 20 zdrojů / zastoupení 14 krajů, offline výstup 113 akcí (+6 proti 107). Původní tabulka a měření níže jsou historická evidence, nikoli tvrzení, že tři nově zastoupené kraje stále nemají zdroj nebo že jsou nyní kompletně pokryté.

## Rozsah a hranice

První rozšiřující dávka pro sezonu **20. 11.–24. 12. 2026**, nikoli úplné pokrytí ČR, měst ani krajů. Živé datum bylo ověřeno systémovým časem. Průzkum proběhl ve všech 14 krajích včetně Prahy. Integrace znamená registraci, přenosné testy, skutečné nalezení detailů ve výpisu a kontrolovaný sběr; samotné nalezené URL nestačí.

Výchozí commit `5caab4e`: programově spočítáno **12 zdrojů, 6 krajů, 78 veřejných akcí**. Nový registr obsahuje **17 zdrojů v 11 krajích**. Původních 12 definic je zachováno beze změny. Nové zdroje nemají žádné bootstrap `seed_urls`: jejich události pocházejí ze skutečných odkazů výpisů.

Všechny HTTP sběry, původní HTML, SQLite, replay manifesty a provozní logy jsou pouze v ignorovaném `private/` tohoto worktree. Žádná produkční databáze/cache, cron, kalendář, formulář, UI ani deployment nebyly změněny. Výstupy testovacích fixture nejsou důkazem živé dostupnosti.

## Mapa všech 14 krajů

Dostupnost níže znamená skutečný přístup primárního HTTP klienta při tomto průzkumu, po kontrole robots.txt. Nejde o dostupnost z vyhledávače. Zkratka „200“ označuje načtený obsah; výjimky jsou výslovně rozlišeny. Vyhledávače a komerční agregátory sloužily jen k discovery, nikoli k potvrzování akcí.

| Kraj | Zdrojů před → po | Ověřené primární URL a dostupnost | Rozhodnutí a zbývající mezera |
| --- | --- | --- | --- |
| Hlavní město Praha | 0 → 0 | https://praha.eu/kalendar-akci — chyba ověření TLS certifikátu, bez vypnutí kontroly. https://prague.eu/robots.txt — 200, `Crawl-delay: 600`; výpis https://prague.eu/cs/akce/ nebyl dokončen. https://praha-dolnipocernice.cz/kalendar-akci — 200 po použití kanonického hostu. | Neintegrováno. PCT by již při několika detailech překročilo stávající rozpočet běhu. Počernice mají jinou drupalovou šablonu; detail ani rok nebyly automaticky přijaty. Prioritní mezera. |
| Středočeský kraj | 2 → 2 | https://www.mesto-beroun.cz/pro-obcany/kultura-sport-a-cestovni-ruch/kalendar-akci/?page=all a https://www.mesto-horovice.eu/volny-cas/kam-za-kulturou-a-kdy/ — živý sběr obou stávajících zdrojů. | Zachovány. Výběr dvou měst není krajské pokrytí; zůstává zejména sever a východ kraje. |
| Jihočeský kraj | 2 → 2 | https://www.budejce.cz/aktuality/121-vanoce-ve-meste-2026 — 200, skutečný odkaz na externí listovací publikaci. Stávající https://www.musobeslav.cz/infocentrum/kalendar-akci/kulturni-akce/ a https://www.itrebon.cz/kalendar.html?page=2 — živý sběr. | Soběslav/Třeboň zachovány. Budějovická publikace není podporovaný detailový kalendář; bez nového adaptéru neintegrována, žádná data z PDF názvu. |
| Plzeňský kraj | 2 → 2 | https://www.visitplzen.eu/akce/gastro-a-trhy/vanocni-trhy/ — 200, explicitně 21. 11.–23. 12. 2026, 10–20 hodin, náměstí Republiky. Stávající Plasy a Černošín ověřeny živým sběrem. | Nový krajský městský portál zatím neintegrován: JSON-LD je `WebPage`, nikoli `Event`; existující WordPress adaptér nelze bezpečně zaměnit. Některé související výlety jsou mimo Plzeň. |
| Karlovarský kraj | 0 → 1 | https://www.karlovyvary.cz/cs/kalendar-akci — robots.txt zakazuje URL, obsah nečten. https://www.nejdek.cz/aktivity/kultura/kalendar-akci/ a jeho detaily — 200; respektován `Crawl-delay: 3`. | **Nejdek integrován** existujícím Galileo adaptérem. Jen přesně ověřená nejdecká místa, nikoli Rudné/Vysoká Pec nebo Nové Hamry. Krajské město zůstává mezerou. |
| Ústecký kraj | 0 → 1 | https://www.usti.cz/cz/volny-cas/kalendar-akci.html — 200, pouze JS shell s `components.calendar.loading`, bez detailových odkazů. https://www.muzeumusti.cz/kalendar-akci/ a https://www.muzeumusti.cz/kalendar-akci/advent-v-muzeu-6/ — 200. | **Oblastní muzeum integrováno** úzce vymezeným WP Event Manager adaptérem. Nejde o městský advent ani celý region. Městský JS kalendář neintegrován. |
| Liberecký kraj | 2 → 2 | https://www.liberec.cz/cz/obcan/?page3=1&page=36 — 200 a skutečný odkaz na https://www.trhyvliberci.cz/advent/program-adventu — 200. Stávající KC Golf Semily a Jilemnice ověřeny živým sběrem. | Liberecký program neintegrován: viditelný výpis používá den/měsíc bez roku; rok se nepřebírá z názvu souboru programu. Zůstává mezera krajského města. Blokované městské Semily se neobcházejí. |
| Královéhradecký kraj | 0 → 1 | https://www.adalbertinum.cz/cs/kalendar-akci.html?mesic=12&rok=2026 — 200, bohatý vložený program, nepodporovaná šablona. https://www.kulturadobruska.cz/kultura-a-sport/kalendar-akci/ a nalezené detaily — 200. | **Dobruška integrována** existujícím Galileo adaptérem. Hradecký inline kalendář zatím neintegrován. U Ledeckého koncertu působí datum zahájení předprodeje jako rozpor parseru; zůstává review, nikoli odhad. |
| Pardubický kraj | 0 → 0 | https://pardubice.eu/kalendar-akci — 200, aktuální obecný výpis bez sezonních detailů v první načtené stránce. https://www.kclanskroun.cz/festival/adventni-lanskroun/ — 200, úvodní termín `29. 11 - 20. 12. 2026`, hlavní text uvádí náměstí J. M. Marků. | Neintegrováno. Chybí přenosně ověřený adaptér s jednoznačnou interpretací zkráceného intervalu a skutečnou discovery detailů, nikoli jen seed festivalové stránky. Prioritní mezera. |
| Kraj Vysočina | 2 → 2 | https://www.jihlava.cz/vismo/kalendar.asp — robots.txt zakazuje URL, obsah nečten. Stávající https://www.telc.eu/turista_a_volny_cas/kalendar_akci/ a https://humpolec.cz/akce/?_hledani=v%C3%A1no%C4%8Dn%C3%AD — živý sběr. | Telč/Humpolec zachovány. Jihlava neintegrována; staré vyhledané adventní články z roku 2025 nejsou důkazem programu 2026. |
| Jihomoravský kraj | 2 → 2 | https://brnenskevanoce.cz/ — 200. https://brnenskevanoce.cz/program/rozsviceni-vanocniho-stromu/ — 301 na https://brnenskevanoce.cz/rozsviceni-vanocniho-stromu/, poté 200. Stávající Rajhrad/Kuřim ověřeny živým sběrem. | Brno má explicitní program, ale jinou sémantiku i přesměrované detaily bez JSON-LD Event. Neintegrováno bez adaptéru; další vhodná dávka ve stávajícím kraji. |
| Olomoucký kraj | 0 → 1 | https://tourism.olomouc.eu/ — 200, skutečné odkazy na program. https://www.vanocnitrhy.eu/ — 200, typ `Festival`, odlišné krajní datum než na městském portálu. https://kultura-hranice.cz/akce/ a ověřené výpisy míst https://kultura-hranice.cz/mista/masarykovo-namesti/ a https://kultura-hranice.cz/mista/evangelicky-kostel/ — 200. | **MKZ Hranice integrovány**, Hranice v okrese Přerov, ne stejnojmenné Hranice u Aše. K zachování rozpočtu se sbírají dva lokální výpisy místo širokého regionálního kalendáře; 14 detailů sdíleno oběma. Olomouc zatím neintegrována. |
| Zlínský kraj | 0 → 1 | https://visitzlin.eu/kalendar-akci a https://visitzlin.eu/kalendar-akci?search=advent — 200. https://visitzlin.eu/kalendar-akci/adventni-zlin-2026 — 200, přesně označená pole Datum/Místo/Vstupné. | **Visit Zlín integrován** pro adventní vyhledávání, nikoli celý kalendář. Obec i konkrétní názvy míst se kontrolují přes allowlist. Další lokality, zoo s více sloty a komplexní odpolední program zůstávají k ověření. |
| Moravskoslezský kraj | 0 → 0 | https://www.ostravskevanoce.cz/ — 200, program není na homepage ve zpracovatelných detailech; samotná dostupnost homepage nestačí. https://www.jeseniknadodrou.cz/obcan/kultura/kalendar-udalosti/ — 200; https://www.jeseniknadodrou.cz/obcan/kultura/kalendar-udalosti/rozsvecovani-vanocniho-stromu-726_129cs.html — 200. | Neintegrováno. Poslední detail je **u kapličky v Blahutovicích**, nikoli uprostřed Jeseníku nad Odrou. Většina výpisu je z okolních obcí; chybí samostatně ověřené geografické výjimky. Prioritní mezera spolu s Ostravou. |

## Bezpečnost nových integrací

- Všechny limity zůstávají 2 výpisy / 14 detailů na zdroj. Žádné zvýšení frekvence, timeoutu ani přidání AI fallbacku.
- Nejdek/Dobruška používají stávající Galileo. `hranice` čte pouze `article.akce-detail` a související vlastní `akce-content`; celé stránky, související program a patička nejsou časovým zdrojem. Řádky `Od - Do` a více začátků zůstávají review, ne falešná jednodenní akce.
- `wpem` úzce normalizuje skutečný nestandardní `Location` a čas `YYYY-MM-DD HH:MM:SS`. Chybějící začátek, konflikt místa, neplatné hodiny či neověřená adresa nejsou přijímány. Zůstává celý označený cenový údaj „od 200 Kč (materiál je v ceně)“, ne domnělá jednotná cena. Poznámka zachovává doporučení od 4 let a rezervaci.
- `visitzlin` čte pouze označený detail a pole Datum/Čas/Místo/Vstupné. Odlišné povánoční období v narativu se neplete s explicitně označeným adventním intervalem. U vícedenních akcí zůstávají společné hodiny null; nejsou tvrzením každodenního otevření. Více samostatných časů znamená review.
- Tři úzká Galileo rozhodnutí jsou navázána na URL, zdroj, název, obě data, původní místo a skutečný sémantický SHA-256: konec nejdeckého zdobení perníčků v 17:00, plná podmínka dětského vstupného v Dobrušce a rozlišení začátku doprovodného programu od rozsvícení stromu.
- Neznámá místa zůstávají v review. Nominatim byl volán sériově s rozestupem alespoň 1,1 s, s privátní cache. Ověřena ČR, přesné město a kraj, typ administrativní město; nikoli první stejnojmenný výsledek nebo SO ORP. Polohy jsou výslovně orientační středy obcí, ne vstupy do budov.

## Geografická evidence

Ověřeno 12. 11. 2026 přes Nominatim; původní JSON odpovědi jsou privátní. Hodnoty přidané do `data/locations.json`:

| Obec | OSM objekt | Rozlišení |
| --- | --- | --- |
| Nejdek | https://www.openstreetmap.org/relation/439476 | okres Karlovy Vary, Karlovarský kraj |
| Dobruška | https://www.openstreetmap.org/relation/440632 | okres Rychnov nad Kněžnou, Královéhradecký kraj |
| Hranice | https://www.openstreetmap.org/relation/438577 | okres Přerov, Olomoucký kraj; nikoli Hranice u Aše |
| Ústí nad Labem | https://www.openstreetmap.org/relation/440166 | Ústecký kraj |
| Zlín | https://www.openstreetmap.org/relation/440910 | Zlínský kraj |

## Snapshoty a bezpečná regenerace po merge

`events.json` a `review.json` zůstávají v PR byte-for-byte původní: 78 akcí a 2 review. Živé rozšířené výsledky se nepublikují a nejsou přidány do historie.

Jediná nezbytná výjimka je malý dodatek do `site/coverage.json`: 5 nových stavů `partial`, **0 veřejných akcí, null kontrolní časy**, jasná poznámka, že jde o historický snapshot čekající na regeneraci, a odpovídající regiony. Původní zdrojové stavy, čas sběru i metriky zůstávají beze změny. Bez této výjimky skutečně selhával `test_real_validator_accepts_existing_public_projection_before_local_push` i `validate_public.py site` na `Inconsistent source scope`. Validator nebyl oslaben ani upraven tak, aby rozpor přehlížel.

Po případném schváleném merge je třeba v koordinaci s vlastníkem publisheru bezpečně regenerovat **všechny tři** JSON z aktuálního registru, pod publikačním zámkem a po kontrole čistého checkoutu, výchozího remote SHA a případného pending stavu. Tento PR nic nemerguje ani nenasazuje. Nezkopírovat naslepo izolovanou DB/cache přes produkční soubory.

Při konfliktu s denním publisherem zachovat aktuální main verze všech tří snapshotů; do nejnovějšího `coverage.json` přidat jen stále chybějící pending zdroje se skutečnou URL z registru. Nepřenášet staré metriky nad nová data. Poté znovu spustit testy a validaci; po merge regenerace vygeneruje konzistentní aktuální trojici. `events.json` a `review.json` se z této větve nepřebírají.

## Zbývající práce

1. Praha, Pardubický a Moravskoslezský kraj stále bez integrovaného zdroje.
2. Doplnit krajská města Karlovy Vary, Hradec Králové, Olomouc a další výše uvedená města pouze s respektováním robots a rozpočtu.
3. Ve stávajících krajích jsou vhodné zejména Brno, Plzeň, Liberec a České Budějovice; jejich nalezení není jejich integrace.
4. Fronta review obsahuje poctivě nepodporované intervaly, neznámá či sousední místa a narativní rozpory; neznamená prokázané zrušení nebo neexistenci programu.
5. Zachovat `complete:false`; větší počet krajů nemění výběrový charakter ani limity discovery.

## Výsledky ověření

Offline replay skutečných zachycených bajtů po opravách: **107 akcí, 11 review, 21 vyřazení, 0 HTTP požadavků**. Původních 78 ID i všechna jejich věcná pole zůstala stejná; čistý přírůstek je **29**. Každá přijatá akce má kontrolu místa, data, hodin a intervalu v [auditu přírůstku](national-event-audit.md). Všech pět nových zdrojů nalezlo skutečné detaily bez seeds.

- Python: **85 testů prošlo**. Přenosné testy nových adaptérů byly doplněny před implementací, včetně pozorovaných RED → GREEN regresí pro neznámá místa/rok, více termínů, obrácené WP timestampy, od/do, dlouhé ceny, přidaný JSON-LD a inkluzivní štítky.
- Po rebase na souběžně doplněný `origin/main` (`a98cc64`) prošlo **18 čistých JS testů** a **27 izolovaných Playwright testů**. Testy nečtou živý katalog a blokují OSM tiles; nejsou ověřením dostupnosti mapových dlaždic.
- Historický public snapshot je validní s 78 akcemi; izolovaný replay s 107. Validator/allowlist nebyly oslabeny. JS syntax kontrolována včetně souběžně přidaných feedback modulů, bez jejich změn v této větvi.
- Nezávislá statická review přes Codex CLI, bez dalšího Hermes agenta: čtyři konkrétní P2 byly opraveny a znovu posouzeny **PASSED** (JSON-LD bypass, zkrácení ceny, slovo od/do před datem a obrácený WP časový interval). Samostatná bounded review změny narativního scope a read-only PR workflow: **PASSED**. Reviewer nespouštěl testy ani síť; exekuční kontroly výše jsou zvláštní důkaz.
- Nový PR workflow spouští offline Python, čisté JS, public validaci a syntax. Má jen `contents:read`, bez Pages oprávnění, uploadu nebo deploy jobu. Původní deploy workflow se touto větví nemění.
- Baseline živý sběr 12 zdrojů: **304,838 s**, 78 akcí. Publisher má beze změny collector timeout **600 s**; skutečná funkce scheduleru `_get_script_timeout()` v aktivním prostředí vrátila **3600 s**. Nastavení scheduleru nebylo měněno.

Dvě **skutečná finální živá měření** po všech opravách a stabilním offline replay, 12. 11. 2026; předchozí vývojové sběry se za tuto dvojici nevydávají:

| Finální kontrola | Začátek (CET) | Celkový runtime včetně validace | Vnitřní runtime collectoru | HTTP / 304 | Akce / review / vyřazení | Chyby zdrojů |
| --- | --- | --- | --- | --- | --- | --- |
| A (izolovaný běh 3) | 18:24:41 | **6 min 44 s** (404,441 s) | 404,004 s | 189 / 13 | 107 / 11 / 21 | 0 |
| B (izolovaný běh 4) | 18:31:25 | **6 min 27 s** (386,681 s) | 385,865 s | 188 / 12 | 107 / 11 / 21 | 0 |

Oba sběry úspěšně skončily a jejich veřejné projekce prošly validátorem. Síť nebyla nahrazena fixtures; standardní HTTP klient respektoval robots a použil izolovanou podmíněnou cache. Oba běhy mají 0 AI volání. Jde o opakování nad již naplněnou izolovanou DB: 107 nezměněných akcí, 0 nově vložených a 0 změněných vůči předchozímu sběru. **Čistý přírůstek 29 je rozdíl proti původním 78**, nikoli zavádějící interpretace počítadla `eventsNew` posledního běhu.

Programově porovnána všechna věcná pole všech 78 původních akcí i všech 107 mezi finálními běhy; měnit se smí jen `verifiedAt`. Všech 29 nových akcí má doložené místo a úplné datum / interval v sezoně; všech 13 hranických programů má po odstranění inkluzivních taxonomických štítků z access scope skutečně `audience:všichni`. Mapové body jsou pouze obecní středy, nikdy z nich nevzniká důkaz přesného místa.

Závěrečná čistá kopie trackovaných/neignorovaných podkladů bez `private/`: znovu 85 Python + 18 JS + public validace (78), bez sítě a bez výzkumné cache. Navíc se beze změny UI vykreslil skutečný historický snapshot (78) i skutečná rozšířená izolovaná projekce (107) v desktopu 1440 px a mobilu 393 px. Všechny čtyři kontroly zobrazily 11 krajů / 17 zdrojů bez JS výjimky, pending text u historického snapshotu byl viditelný a nový filtr Hranic vracel 13 akcí. Externí API a mapové tiles byly v této kontrole blokované.

Nejdelší finální sběr se vešel do stávajícího 600s timeoutu. Naměřený čas není záruka pro další rozšiřování nebo výpadky cizích serverů; další dávka musí rozpočet znovu změřit. Implementace, registry, geodata, testy i read-only PR workflow po zmrazení před finální dvojicí nebyly měněny, doplňuje se jen tento protokol.

Při obnovení CLI byl existující proces `proc_7bf993a3edc2` potvrzen jako dokončený s kódem 0. Uložené výstupy obou běhů byly znovu validovány a porovnány se základními 78 akcemi i vzájemně, včetně shody zmrazených hashů zdrojových souborů a kontroly izolovaných cest. Žádný další sběr ani nová implementace nebyly spuštěny. Celkový čas v tabulce podle runneru zahrnuje subprocess i následnou public validaci; vnitřní čas collectoru je uveden samostatně.
