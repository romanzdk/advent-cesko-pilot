# Provoz a ověření

Tento dokument je určený ke správě autorizované pracovní kopie projektu. Veřejné zpřístupnění příkazů neuděluje právo provozovat vlastní kopii; podmínky jsou v [LICENSE](../LICENSE).

## Co kde běží

- Python sběrač a publisher běží na lokálním serveru. Produkční publisher používá POSIX zámek `fcntl`, Git a autentizovaný GitHub CLI `gh`.
- Hermes pouze plánuje spuštění skriptu v režimu `no_agent`. K samotnému sběru nejsou potřeba LLM ani API klíče pořadatelů.
- GitHub Actions provede kontroly a nasadí pouze `site/` na GitHub Pages.
- Návštěvníkův prohlížeč načítá statické soubory a mapové dlaždice; pro dobrovolná hlášení používá oddělené veřejné přijímací rozhraní. Nemá přístup k interním databázím ani správě infrastruktury.

Sběrač používá standardní knihovnu Pythonu. Aktuální prostředí bylo ověřené s Pythonem 3.14.9 a Node.js 26.12.1; nejde o prohlášení, že starší vydání nejsou podporovaná. Prohlížečové testy mají samostatnou závislost Playwright v `tests-ui/package.json`.

## Lokální náhled již publikovaných dat

Příkaz nemění data a nespouští sběr ani publikaci:

```sh
python3 -m http.server 8000 --bind 127.0.0.1 --directory site
```

Otevřete `http://127.0.0.1:8000/`. JavaScriptové moduly potřebují HTTP server; otevření `index.html` přes `file://` není rovnocenný náhled. Mapový podklad vyžaduje připojení k internetu.

## Kontroly bez publikace

Z kořene pracovní kopie:

```sh
python3 -m unittest discover -s tests -v
node --test tests-ui/helpers.test.mjs tests-ui/pilot.test.mjs tests-ui/feedback.test.mjs
python3 scripts/validate_public.py site
python3 scripts/publish_daily.py --check
```

`--check` ověřuje pouze přítomnost potřebných místních modulů. Nesbírá, nespouští Git ani síťové operace a není důkazem funkční autentizace či dostupnosti zdrojů.

Úplná sada izolovaných Chromium testů:

```sh
npm install --prefix tests-ui
cd tests-ui
npx playwright install chromium
npm test
```

Pokud na daném systému chybí systémové knihovny Chromium, je třeba je zajistit zvlášť; zdejší příkazy je neslibují nainstalovat. Browser testy mají vlastní prohlížeč, kontexty a lokální fixture server. Nejde o procházení uživatelovy přihlášené relace.

V čistém checkoutu testy používají přenositelné faktické HTML fragmenty. Tam, kde jsou dostupné původní soukromé podklady, doplňují lokální ověření; celé zachycené stránky se do veřejného repozitáře nekopírují.

## Poloha v prohlížeči

Poloha se žádá jednorázově přímo po skutečném kliknutí na „Akce v mém okolí“, nikoli přes předběžnou kontrolu oprávnění. Souřadnice se neukládají ani neodesílají a nepoužívá se náhradní zjišťování podle IP adresy.

Nativní limit 10 sekund se vztahuje k určení polohy, ne čekání na povolení. Samostatný JavaScriptový limit proto po 10 sekundách jen ukáže čekání a až po minutě ukončí neodpovídající pokus. Zrušení/reset/permalink stále ignorují opožděné odpovědi; při úspěchu, chybě nebo výjimce se oba časovače vyčistí. Zachycená synchronní výjimka není vydávána za timeout.

Při selhání nabízí stránka „Podrobnosti o poloze“: původní kód a omezenou zprávu prohlížeče, dobu čekání, zabezpečený kontext, viditelnost, vložení do rámce a pravidla dokumentu, pokud je prohlížeč zpřístupní. Údaje zůstávají pouze v aktuální stránce, bez souřadnic či automatické telemetrie. Kód 1 sám o sobě nedokazuje ruční zamítnutí uživatelem; nepřítomnost podpory kontroly pravidel znamená neznámý stav, nikoli zákaz. Web neumí vynutit systémový dialog.

Izolované testy ověřují pomalou odpověď, rozlišení chyb, výjimky, rušení a rozložení na úzkém displeji; nenahrazují ověření oprávnění na fyzickém iPhonu. Pokud tam problém trvá, je potřeba nejprve přesná místní diagnostika, nikoli další změny parametrů či opakované automatické žádosti naslepo.

## Samostatný sběr

Následující příkaz provádí skutečné HTTP požadavky a mění lokální evidenci i tři veřejné JSON soubory, ale neprovádí Git commit ani push:

```sh
python3 scripts/collector.py --registry data/sources.json \
  --db private/events.sqlite --cache private/http-cache \
  --output site --locations data/locations.json
python3 scripts/validate_public.py site
```

Pro omezenou kontrolu lze doplnit `--source-id ID`. Přesná ID jsou v `data/sources.json`. Ostatní uložené události z registrovaných zdrojů zůstávají zachované.

Sběrač vypisuje JSON metrik; ten je provozním výstupem, nikoli zprávou pro uživatele. Fatální chyba konfigurace či úložiště končí nenulovým návratovým kódem. Dílčí výpadek zdroje může vrátit nulu a být zapsaný jako `error` či `partial` v pokrytí; samotný návratový kód proto nedokládá dostupnost všech zdrojů.

**Pozor:** po samostatném sběru jsou veřejné soubory rozpracované. Denní publisher záměrně odmítá nečistou pracovní kopii. Nepouštějte samostatný sběr v jeho produkčním checkoutu bez plánu, jak výsledky zkontrolovat a autorizovaně publikovat; pro experiment použijte vlastní oddělený pracovní adresář a výstupy.

## Pouze aktualizace redakčního výběru

`--reviewed-only` je výslovná volba sběrače i publisheru; bez ní zůstává plný sběr. Přeskočí HTTP načítání všech běžných zdrojů, nikoli jejich registraci nebo veřejnou projekci. Jejich uložené akce, kandidáti a časy poslední kontroly se zachovají; výstup dál obsahuje celý registrovaný katalog. Metriky požadavků popisují jen tento průchod, nikoli nové ověření zachovaných pořadatelů. `--source-id` případně dále omezuje pouze vybraný redakční zdroj.

Izolovaný sběr s **kopií odpovídající existující SQLite** a schválenou soukromou konfigurací (prázdná DB nedokáže obnovit ostatní akce):

```sh
python3 scripts/collector.py --registry data/sources.json \
  --db private/events.sqlite --cache private/http-cache \
  --output private/validated-output --locations data/locations.json \
  --reviewed-feed-config private/reviewed-feed.json --reviewed-only
python3 scripts/validate_public.py private/validated-output
```

Pro autorizovanou publikaci z čisté produkční větve `main` použijte `python3 scripts/publish_daily.py --reviewed-only`. Publisher automaticky předá existující `private/reviewed-feed.json`; zachová sezonní pojistku, zámek, kontrolu čistoty a původu, vlastnictví pending commitu i ověření Pages. Pending obnova vždy dokončí původní commit bez nového sběru, bez ohledu na nově zvolený režim. `--check --reviewed-only` zůstává pouze místní kontrolou připravenosti. Samotné přidání volby nemění plánovač ani jeho výchozí plný sběr.

Před přenosem nového feedu zkontrolujte přesné vazby hostitel–obec–poloha a případnou změnu vlastnictví existujícího stabilního ID. Tu striktní adaptér úmyslně odmítá: pod publikačním zámkem zálohujte SQLite, ověřte nepřítomnost pending stavu a proveďte jen předem auditovanou transakční migraci `events.source_id` s podmínkou ID a původního vlastníka a kontrolou počtu řádků. Neměňte ostatní události, historii, revizní stavy ani guard vlastnictví; DB nemažte. Pak proveďte dva izolované průchody se stejným registrem/feedem, validujte všechny tři JSON a porovnejte sémantické hodnoty i zachování všech ostatních záznamů, teprve poté publikujte.

Redakční skupiny pro `www.zus-popo.net` / Velké Popovice, `www.osadaladvi.cz` / Ládví, `www.strancice.cz` / Strančice a `www.krestanskevanoce.cz` / Hrusice pokrývají schválený veřejný přenos, ne crawl těchto webů. Ládví a Strančice mají neznámou polohu, nikoli domyšlené souřadnice. Aktuální počty a stav přenosu se odvozují z publikovaného pokrytí. Aktualizace je pouze webová: žádné zápisy do kalendářů ani pozvánky; kalendářní omezení nejsou filtrem webových kategorií či obcí.

## Celý publikační průchod

Z čisté produkční pracovní kopie:

```sh
python3 scripts/publish_daily.py
```

Skript:

1. Zkontroluje letošní sezonní limit ještě před procesy a síťovými operacemi a získá neblokující lokální zámek.
2. Vyžaduje větev `main`, čistý checkout a přesný nakonfigurovaný vzdálený repozitář.
3. Provede sběr a validaci veřejných dat.
4. Vytvoří commit pouze ze `site/events.json`, `site/coverage.json` a `site/review.json` a odešle ho.
5. Ověří vzdálený HEAD, úspěšný Pages workflow pro daný commit a shodu všech tří skutečně publikovaných JSON s lokálními soubory.

Úspěšný běh záměrně nic nevypisuje. Při chybě vrací nenulový kód a stručnou zprávu bez syrových výjimek či přihlašovacích údajů. Plánovač chybu doručí správci.

Cílový repozitář a veřejná adresa jsou v publisheru pevně vymezené. Není to univerzální deploy nástroj ani návod k provozování cizí kopie.

## Denní plán a konec sezony

Úloha je nastavená na **08:30 Europe/Prague**, od **13. listopadu do 24. prosince 2026**. Konfigurace plánovače a krátký spouštěcí wrapper jsou spravované mimo tento repozitář. Díky režimu `no_agent` se při této aktualizaci nevolá LLM.

Po 24. prosinci 2026 publisher neprovede sběr ani publikaci, i kdyby se spustil opožděně. Sezonní pojistka patří publisheru; samostatný CLI sběrač se řídí datovým oknem registru, nikoli aktuálním dnem spuštění.

## Selhání a obnova

- Po nedostupnosti zdroje zůstávají poslední dobré události a pokrytí ukazuje chybu. Odstraněná stránka sama o sobě nepotvrzuje zrušení akce.
- Pokud nově načtená stránka přinese nejasné či rozporné údaje, položka se stáhne do kontroly.
- Při neúspěšném push nebo ověření nasazení zůstává soukromý vlastnický stav známého commitu. Další průchod ověřuje stejný commit, bez nového sběru či duplicitního commitu.
- Pokud přerušený sběr zanechá nečisté veřejné soubory nebo proces skončí mezi vytvořením commitu a uložením vlastnického stavu, následující průchod bezpečně odmítne automatickou opravu. Je nutná ruční kontrola konkrétního diffu a HEAD. Nepoužívejte plošný reset nebo stash vedle nesouvisející práce.

## Přidávání zdrojů

Registr a aktuální veřejné pokrytí se odvozují z `data/sources.json` a posledního validovaného sběru, nikoli z historického počtu zdrojů. Validátor ověřuje přesná ID zdrojů, jejich kraje, obce i přiřazení zdrojových URL; pro izolované testy lze `validate_directory(path, registry=...)` předat jiný registr. Rozhraní odvozuje souhrn pokrytí z veřejných dat. Přidání kraje proto nevyžaduje přepsat pevný počet, ale stále vyžaduje zdrojové a geografické ověření.

Redakčně ověřené veřejné záznamy mají samostatný striktní adaptér a výslovné vazby na primární hostitele, obce a polohy. [Trvalý přenos a jeho limity](content-repair.md) popisuje soukromou provozní konfiguraci, zachování původního `verifiedAt`, odstranění záznamů, výpadky i rozdíl mezi kontrolou přenosu a novým ověřením pořadatele. Konfigurace musí být přenesena společně s odpovídající SQLite pod publikačním zámkem; není součástí veřejného repozitáře.

Šest nových zdrojů používá `allowed_venues`: seznam přesně ověřených míst v obci, porovnávaný po normalizaci NFKC, mezer a velikosti písmen. Nové či změněné místo čeká na kontrolu; seznam není obecný geokodér ani oprávnění přiřadit sousední obec ke zdroji. Podklady pro přidání místa nejprve ověřte u pořadatele. Automatické objevování nových akcí na již ověřených místech zůstává funkční.

Nový zdroj musí mít ověřenou lokalitu, současný rok v obsahu, povolené automatické načítání a regresní podklad pro jeho formát. Každé rozšíření projde skutečným sběrem a opakovaným průchodem bez nových duplicit. Rozsah se na webu označuje jako výběr, nikoli úplný krajský katalog.

## Ruční kontrola kandidátů

Historická dávka 37 položek byla zkontrolována 12. listopadu 2026: 21 přijatých, 14 vyřazených a dvě zadržené akce. Není to aktuální velikost fronty po rozšíření zdrojů. Aktuální nepublikované kandidáty a důvody obsahuje `site/review.json`; rozhodnutí a opravy se ukládají do `event_reviews` příslušných zdrojů, nikoli do ručně přepsaného veřejného JSON.

Před novým rozhodnutím načtěte aktuální primární detail, ověřte rok, celý interval a skutečnou obec a případně plakát. Pro výpočet `contentHash` použijte exportovanou funkci `review_fingerprint(body, adapter)` nad týmiž původními bajty. Zachovejte původní hodnoty v `expected*`, přesnou URL a ID zdroje; `overrides` slouží jen doloženým opravám. `verifiedTown` přidávejte pouze po ověření obce, ne podle sídla vydavatele. U polí z plakátu připojte zdrojový odkaz a datum ověření do poznámky.

Nejdřív přehrajte zachycené detaily bez sítě v oddělené kopii a porovnejte všechny původní veřejné záznamy. Teprve potom proveďte závěrečné živé sběry a přeneste schválené soubory i odpovídající interní evidenci do produkce. Zamítnutí neplatného rozhodnutí musí stáhnout dříve publikovanou akci do kontroly; nesmí předstírat běžný výpadek zdroje.

## Veřejné tipy z webu

Panel „Chybí vám akce nebo obec?“ nabízí plný návrh a rychlý tip. U karet je také „Nahlásit chybu“ s kontextem podle ID z aktuálního veřejného katalogu. Odeslání bez účtu jde přes izolovaný HTTPS receiver do trvalé SQLite fronty; pouze soukromý worker může vytvořit issue v pevném repozitáři. Zdrojové URL se nikdy nenačítají. Každé podání vyžaduje souhlas s veřejným GitHub zveřejněním a upozornění bez osobních údajů. Katalog, kalendáře a pozvánky se návrhem nemění.

Přijato / čeká ve frontě, nejisté odeslání a ověřené zveřejnění jsou odlišné stavy. Potvrzený odkaz se ukáže až po přesném readbacku issue. Po přijetí či nejednoznačné odpovědi se blokuje ruční záloha a nové podání; opakování ověřuje stejné ID, ne další kopii. Rozpracované opravy jsou svázané s konkrétní akcí i při přepnutí dialogu nebo přidání dalších karet do seznamu. Manuální návrh na GitHubu před přijetím zůstává dostupný a vyžaduje účet a konečné potvrzení návštěvníka.

[Veřejný postup a obecné bezpečnostní hranice](feedback-api.md) vysvětlují příjem, frontu a odděleného odesílatele bez přístupových údajů v prohlížeči. Konkrétní serverové cesty, interní síť a příkazy pro správu tohoto nasazení zde nerozepisujeme; úplná provozní konfigurace a obnovovací poznámky se vedou neveřejně mimo repozitář. Adresa veřejného přijímacího rozhraní zůstává zjistitelná z klientského kódu a síťových požadavků. Ochrana musí vycházet z oddělení oprávnění, validace a provozních kontrol, ne z utajení této adresy. Fronta se při aktualizaci nesmí mazat ani obnovovat ze staré kopie kvůli opakování. Kontrola dostupnosti příjmu sama nepotvrzuje dostupnost odesílatele ani GitHubu.

Základní ochrany zahrnují podepsaný jednorázový challenge, omezenou velikost/počet požadavků a globální limit přijetí; nejsou silnou ochranou proti botům. Frontu a její kapacitu je nutné provozně sledovat. Návrhy a odkazy jsou nedůvěryhodná data, nikoli instrukce nebo automatické vstupy sběrače. Před zařazením se ověří primární zdroj, rok, termín, lokalita a duplicity.

Nedávná veřejná hlášení se načítají až po otevření panelu veřejným GitHub API bez cookies. Jde nejvýše o deset položek, ne úplnou kontrolu duplicit. Běžné browser fixture testy nic veřejně nevytvářejí; produkční smoke test musí být výslovně označený technický test, jeho issue se přesně přečte zpět a následně uzavře. Úspěšné mockované testy, loopback API a veřejné E2E nejsou zaměnitelné důkazy.

## Sdílení a vizuální podklady

`site/social-preview.png` je značková ilustrace 1280 × 640 px, nikoli screenshot aplikace. Zdroj je v `docs/social-preview.html`; obrys ČR vychází z Natural Earth (public domain) a orientační body z registrovaných obcí v `data/locations.json`. Obrázek je použitý v README a v metadatech Open Graph / Twitter Card. Absolutní image URL míří na veřejný soubor v repozitáři, aby byla dostupnost obrázku nezávislá na DNS webové domény. Samotná stránka pro náhled sdíleného webu stále musí být dostupná.

Vlastní náhled **repozitáře** se na GitHubu nastavuje zvlášť v *Settings → General → Social preview*. Nestačí pouze commitnout obrázek nebo přidat metadata webu. Pro upload použijte tentýž PNG, který je hluboko pod limitem GitHubu 1 MB; poté ověřte `usesCustomOpenGraphImage` a výsledný `openGraphImageUrl` přes GraphQL. Bez tohoto ověření neslibujte nastavený vlastní obrázek repozitáře.

ICS export používá `PRODID:-//Advent v Cesku//CZ` a stabilní UID ve tvaru `eventId@advent-cesko-2026`. Při opakovaném importu starších souborů s jiným jmenným prostorem mohou vzniknout duplicity. Před novým importem zkontrolujte dříve ručně přidané položky; žádné cizí ani osobní kalendáře se tímto projektem automaticky nemění.

## Dokumentační obrázky

`docs/assets/desktop.png` a `mobile.png` jsou skutečné screenshoty veřejného webu z 12. listopadu 2026. Desktop ukazuje výchozí přehled, mobil filtr rozsvícení stromů. Nejde o fixture server ani upravená ukázková data.

`docs/assets/architecture.png` je vykreslené schéma z [architecture.html](architecture.html). HTML obsahuje inline SVG, funguje bez externích knihoven a lze ho otevřít samostatně. Obrázky nejsou součástí Pages artefaktu, protože nasazení nadále publikuje jen `site/`.
