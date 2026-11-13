# Deterministický sběrač událostí

Sběrač používá standardní knihovnu Pythonu, bez AI volání. [README](../README.md) představuje projekt, [provozní dokumentace](../docs/operations.md) popisuje příkazy a publikaci.

## Vstupy a výstupy

- `data/sources.json`: sezona, datové okno, registry zdrojů, detailní URL, adaptéry a případná ověřená geografická přiřazení.
- `data/locations.json`: ověřené veřejné polohy. Klíčem může být obec nebo samostatný identifikátor místní části použitý konkrétním geografickým přiřazením.
- `private/events.sqlite`: interní události, stavy zdrojů, pozorování, původ údajů, nevyřešené kandidáty a známá vyřazení.
- `private/http-cache/`: přesné původní adresy, validační HTTP hlavičky, zachycený obsah a jeho SHA-256.
- Výstupní adresář: `events.json`, `coverage.json`, `review.json`. Veřejné záznamy neobsahují interní kalendářní metadata, přihlašovací údaje ani lokální cesty.

Veřejný export je oddělený od ukládání interní evidence. `scripts/validate_public.py` před publikací kontroluje uzavřenou množinu povolených polí a formát údajů.

## Objevování a HTTP

Výchozí limit zůstává dvě stránky výpisu a čtrnáct detailních URL na zdroj. Registr může výslovně nastavit `max_index_pages` (celé číslo 1–4) a `max_details` (1–40); neplatné typy včetně booleanů nebo hodnoty mimo rozsah zastaví sběr před načítáním. Telč, Humpolec a Hranice mají 40 detailů; Jilemnice, Hořovice, Třeboň, Nejdek a Radotín čtyři výpisy. Nejde o neomezené procházení. Sběrač sleduje skutečné odkazy na stejném hostiteli, filtruje je podle registru a sezonního popisku. Nové odkazy mají přednost před bootstrap URL; známé uložené detaily se znovu kontrolují v rámci stejného limitu. Zachovává původní percent-encoding adres. Efektivní stropy jsou ve stavech zdrojů i souhrnné poznámce.

Zdroje na různých hostitelích se stahují souběžně (nejvýše 8 vláken); jeden hostitel zůstává na jednom vlákně, takže rozestupy i robots.txt platí beze změny. Zpracování a zápis do SQLite běží dál postupně v pořadí registru.

Před čtením kontroluje robots.txt. Používá HTTPS, omezená přesměrování na stejném hostiteli a alespoň 1,05 s mezi dokončením a dalším požadavkem na hostitele; delší limity robots.txt respektuje. Obsahový požadavek má timeout 15 s, limit 2 MiB a nejvýše dva pokusy. ETag a Last-Modified umožňují podmíněné GET. Při HTTP 304 se znovu použijí původní bajty po kontrole otisku.

## Adaptéry a důkazy

Přednost má JSON-LD se skutečným typem `Event`, nikoli jiné strukturované bloky na stránce. Adaptér zpracuje explicitní termíny, časová pásma, obec konání, zveřejněné cenové varianty v CZK a informaci o zrušení. Z dostupnosti uvedené v nabídce nedělá tvrzení o skutečně ověřeném počtu vstupenek.

HTML adaptéry čtou pouze vymezené části:

- Galileo: `.event-detail` a známá pole termínu a místa.
- Vismo: `#akce` a `#zahlavi`; adaptér zůstává testovaný na starších podkladech, ale městské Semily se jím živě nečtou.
- Drupal: tělo `main`, explicitní pole krajních termínů a místo konání.
- WordPress: obsah článku; u rajhradské šablony oddělený od publikačních metadat.
- IKS Třeboň (`itrebon`): `table.kal-info-detail`, explicitní pole termínu a místa; výchozí půlnoc není potvrzená hodina.
- Telč (`telc`): detail v `.clanek_levy_sloupec`, úvodní úplná data, označené místo a hodiny v programu; boční kalendář se nepoužívá.
- Humpolec (`humpolec`): `main.single.event`, metadata `aside#meta .meta-items` a vlastní tělo bez souvisejících akcí. Více termínů či začátků se podrží k ověření.
- Hranice (`hranice`): označené řádky `article.akce-detail` a vlastní `.akce-content`. Termín musí být jediný úplný den, případně s vyjmenovaným českým názvem dne. `Od - Do`, neúplné intervaly a více začátků zůstávají k ověření. Inkluzivní taxonomické štítky „pro seniory“ nejsou zákazem účasti jiných návštěvníků.
- WP Event Manager (`wpem`): jediný JSON-LD Event, nestandardní `Location`, úplné lokální timestampy se sekundami; konec nesmí předcházet začátku. Cena z vlastního označeného bloku zachovává i „od“ a podmínky. Z krátkého popisu se přenáší očištěná poznámka o programu a podmínkách účasti.
- Visit Zlín (`visitzlin`): `section.site-event .event`, pouze označená pole Datum/Čas/Místo/Vstupné. Hodiny vícedenních programů se nepovažují za jeden začátek/konec; jiná období v narativu nejsou přimíchána do označeného intervalu.
- Lanškroun (`lanskroun`): jediný `.festival-top__content`, označený nadpis, krátký popis a celý interval s výslovným společným rokem v témže poli. Rok není převzat z URL/galerie/patičky. Přijímá jen ověřené náměstí J. M. Marků, bez domýšlení denních hodin nebo ceny; další úplný numerický termín v krátkém popisu či nové cenové podmínky v nadpisu/popisu znamenají Review. Historická galerie a hodiny pokladny nejsou scope události.

- DRE / Public4u (`dre`): nadpis `.nadpis_clanku` a pouze označená pole `table.kratky_popis_akce` (Místo konání, Datum konání). Přijímá jediný den s volitelným „od HH:MM (do HH:MM) hodin“ nebo výslovný interval „D.M.RRRR až D.M.RRRR“; více termínů v poli nebo přidaný JSON-LD Event znamená Review. Tato města sdílejí hosting, který na souběžné požadavky odpovídá HTTP 429, proto se všechny `dre` zdroje stahují v jednom vlákně za sebou.
Nové HTML adaptéry Hranic, Zlína a Lanškrouna při nečekaném přidání JSON-LD Event přejdou do kontroly, aby obecná strukturovaná větev neobešla jejich intervalové a místní kontroly. Všechny tři adaptéry první dávky posílají cenové pole nad 180 znaků do kontroly místo tichého odříznutí posledních cenových variant; Lanškroun drží jakékoli nově přidané cenové podmínky. Původní adaptéry a jejich chování zůstávají zachované.

Rok se neodvozuje z URL, patičky ani data publikace článku. Chybějící či rozporný údaj znamená ruční kontrolu, datum mimo sledované období známé vyřazení. Půlnoc používaná CMS jako výchozí hodina zůstává neznámým časem. Krajní termíny vícedenních akcí nenahrazují otevírací dobu.

Přesné geografické přiřazení URL je podmíněné shodou zdroje, normalizovaného pole místa a ověřeného data. Místní části Plas proto používají vlastní orientační polohy. Změna podkladů přiřazení zneplatní a položka se vrátí do kontroly; nejde o obecný automatický geokodér.

Nových šest zdrojů v Berouně, Hořovicích, Soběslavi, Třeboni, Telči a Humpolci má navíc `allowed_venues`: přesně ověřené názvy míst v obci. Porovnání normalizuje NFKC, mezery a velikost písmen, nikoli význam nebo adresu. Neznámé místo zůstává k ověření, aby regionální kalendář nevydával akce sousedních obcí za místní. Toto omezení nebrání objevování nových akcí na již ověřeném místě.

## Ověřená rozhodnutí a opravy jednotlivých akcí

Registr může u zdroje obsahovat `event_reviews` podle přesné zdrojové URL. Rozhodnutí `accept`, `exclude` nebo `hold` je podmíněné shodou zdroje, jeho obce, názvu akce, obou termínů, původního místa a otisku sémantického textu. `review_fingerprint` nečte navigaci, související programy ani kontakty pořadatele v telčské šabloně. Otisk zachovává velikost písmen a diakritiku, sjednocuje pouze bílé znaky. Změna ověřovaného obsahu uvnitř sezonního okna vrací položku do kontroly; nejde o trvalé vynucení starých údajů.

Přijaté rozhodnutí může upravit jen uzavřenou množinu polí: začátek, konec, místo, kategorii, cenu, podmínku registrace, zaměření a poznámky. Samostatně ověřené město dovoluje výjimku pro jedinou akci s obecným zdrojovým místem `jiné`; tento řetězec se nikdy nepřidává do obecného seznamu míst. Soukromé cesty ani e-maily se do veřejných polí nepřenášejí. Doplňky převzaté z plakátů mají v poznámce uvedené datum ověření.

Chybný typ seznamu rozhodnutí nebo prázdný záznam znamená ruční kontrolu, nikoli síťový výpadek zachovávající starou veřejnou položku. Jednoznačné datum mimo okno se vyřazuje před kontrolou lokality, takže známé vyřazení nezůstává zbytečně ve frontě. Třeboň a Telč podporují výslovný interval dvou úplných dat; různé telčské denní hodiny se nepřevádějí na jediný společný čas. Více samostatných představení na jedné URL se nadále podrží k rozdělení.

## Identita, změny a selhání

SQLite uchovává stabilní identifikátor odvozený z přesné zdrojové URL a otisk věcného obsahu bez času kontroly. Rozlišuje nové, změněné a nezměněné položky. Původ důležitých polí se zapisuje se zdrojem a pozorováním; pro dodatečný podpůrný zdroj se nevymýšlí hash nezachycené stránky.

Při chybě načtení zůstávají poslední dobré události. Při nově načtené nejednoznačné revizi se stará veřejná položka stáhne do kontroly. Odstranění stránky samo o sobě není zrušením akce. Zájezdy a termíny mimo rozsah se evidují jako vyřazení, odděleně od nevyřešených kandidátů.

Deduplikace porovnává obec, místo, datum, název a začátek. Záznamy bez uvedeného místa se neslučují jen podle názvu. Zdrojové počty mohou před deduplikací převyšovat počet veřejně publikovaných událostí.

## Testování a omezení

`--offline-fixtures MANIFEST.json` mapuje přesné URL na soubory relativně k manifestu. Při chybějícím podkladu nevzniká síťový fallback. Čistý checkout obsahuje malé faktické fragmenty; původní úplné zachycené stránky zůstávají soukromé. Testy a jejich podklady nejsou vydávané za úspěšný živý sběr.

Projekt nemá obecné OCR plakátů, import libovolných PDF, Facebook, přihlašování, odvozování termínů z RSS publikačních dat ani AI fallback. Omezené procházení nikdy neopravňuje tvrdit úplnost regionu; `coverage.json` výslovně uvádí `complete: false`.

Průzkum všech krajů, skutečně integrované a blokované zdroje, podklady geodat, izolovaná měření a regeneraci historických snapshotů popisuje [celostátní source audit](../docs/national-source-audit.md). Pět přidaných zdrojů má prázdné seeds a používá přesný venue allowlist; Hranice mají dohromady dva lokální výpisy a sdílený limit 40 detailů.

[Druhá dávka](../docs/national-wave2-audit.md) přidává další tři seedless zdroje: Praha 16 / Radotín a Štítina používají nezměněný Galileo; KC Lanškroun vlastní úzký festivalový adaptér. Všechny tři mají přesný venue allowlist; Radotín nyní nejvýše 4 výpisy / 14 detailů, ostatní 2 / 14. Každá nově přijatá akce je auditovaná zvlášť; reprezentace všech krajů není kompletní pokrytí.

## Schválený veřejný redakční výběr

Adaptér `reviewed-public` není dalším HTML crawlerem a nečte soukromý kalendář. Přenáší pouze uzavřené veřejné schéma z již schváleného `data/reviewed-events.json` nebo z vlastněného veřejného feedu určeného soukromou místní konfigurací. V registru jsou primární hostitelé, výslovné obce/kraj, schválené polohy s OSM původem a jediná explicitně povolená fragmentová URL. Neznámá obec, hostitel nebo změněné geosouřadnice vyžadují kontrolu; neprobíhá automatické odvozování kraje ani geokódování. Původní ID, časy, podmínky, intervaly a `verifiedAt` se zachovávají.

Výchozí snapshot se do SQLite vloží jen jednou pro každý registrovaný redakční zdroj. Úspěšný feed nahrazuje jeho množinu záznamů, včetně odstranění a prázdného seznamu. Síťový výpadek uchová poslední přijatý stav; chybějící konfigurace ani další spuštění neobnoví odebrané položky ze snapshotu. Změněný neplatný záznam se stáhne do kontroly, ostatní platné záznamy mohou zůstat. Neplatný kořen nebo starší revize stáhne celý dotčený redakční výběr; nejvyšší přijatý čas revize přetrvá. Stejný timestamp smí opakovat stejný obsah, ne odlišnou revizi.

`reviewed_state` uchovává bootstrap/revizní stav a `reviewed_provenance` skutečný hash přenesených bajtů, soukromou URL přenosu, čas přenosu a původní datum důkazu. V běžné provenienci primárních polí zůstává hash nenačtené stránky `NULL` a datum původní: kontrola feedu není ověřením pořadatelského webu. Veřejný stav používá primární URL a výslovně vysvětluje význam časů kontroly.

Pouze tato registrovaná větev dovoluje veřejné delší kurátorské popisy do 1000 znaků a zachování konce již schváleného prosincového intervalu až do 31. prosince; začátek musí zůstat v sezonním okně. HTML adaptéry mají dál původní 200znakový popis a termíny uvnitř okna. Důvodem je nezkrátit důležité podmínky ani nevymyslet dřívější konec výstavy.

Konfiguraci a offline regresní příkazy popisuje [oprava trvalého obsahu](../docs/content-repair.md). Publikační podproces má pro rozšířený, stále sekvenční sběr timeout 1800 s; zámek, Git ochrany, HTTPS/robots politika a plánovač se nemění.
