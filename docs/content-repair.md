# Trvalý veřejný redakční obsah a rozšířené limity sběru

## Co je a není importováno

`data/reviewed-events.json` je verzovaný, reprodukovatelný snapshot **51 již veřejných záznamů**. Zachovává všechny původní veřejné hodnoty včetně stabilních ID, dat důkazů, neznámých hodin, podmínek účasti, geodat a celého intervalu výstavy do 31. prosince. Jediným doplněným polem každé akce je výslovně přezkoumaný `region: Středočeský kraj`. Osm původních popisů je delších než 200 znaků; jejich důležité podmínky se nezkracují.

Nečte se soukromý kalendář, nedoplňují se kalendářní identifikátory, účastníci ani kontakty. Snapshot není prohlášen za nové živé ověření jednotlivých pořadatelských stránek. Adaptér rovněž neobchází zákaz načítání sociálních sítí nebo PDF: pouze přenáší schválená veřejná fakta a primární odkazy.

Původní bootstrap registr obsahoval **22 primárních hostitelů a 17 výslovných obcí**, bez překryvu s původními živými adaptéry. Aktuální registr navíc schvaluje hostitele `www.zus-popo.net` pro Velké Popovice, `www.osadaladvi.cz` pro Ládví, `www.strancice.cz` pro Strančice a `www.krestanskevanoce.cz` pro Hrusice; postup omezené aktualizace a migrace vlastnictví popisuje [provozní dokumentace](operations.md#pouze-aktualizace-redakčního-výběru). Polohy jsou přesné veřejné OSM podklady z těchto záznamů v `allowed_locations`; nejsou odvozovány z hostitele nebo názvu kraje. Při změně souřadnic nebo nové obci je nutná nová cílená kurace registru. Dvě schválené fragmentové primární URL (Webooker a EduPage) jsou výslovně v `allowed_fragment_urls`; nepovolují se fragmenty plošně. Platný záznam bez polohy může zůstat bez bodu na mapě.

## Aktivace denního přenosu

Provozovatel uloží do **soukromého** `private/reviewed-feed.json` přesně tento tvar s vlastněnou, předem schválenou HTTPS adresou:

```json
{"url":"https://owned.example.cz/events.json"}
```

Jde o tvar konfigurace, nikoli skutečný endpoint. Skutečná adresa patří jen do soukromých provozních nastavení/evidence, ne do veřejného registru nebo prezentace. Nepřijímá se adresa z návštěvnického tipu. Soubor musí být při přenosu do produkce zkopírován výslovně; vhodná oprávnění jsou 0600, adresář 0700.

`publish_daily.py` existující soubor automaticky předá sběrači. Pro ruční spuštění:

```sh
python scripts/collector.py \
  --registry data/sources.json --db private/events.sqlite \
  --cache private/http-cache --locations data/locations.json \
  --output private/validated-output \
  --reviewed-feed-config private/reviewed-feed.json
python scripts/validate_public.py private/validated-output
```

Bez nastavení se na čerstvé databázi vloží schválený snapshot a veřejný stav je `partial`, s prázdným `lastSuccess`. Bootstrap se pro každý zdroj provádí jen jednou. Po prvním přijatém feedu se při výpadku nebo ztrátě konfigurace používá pouze poslední databázový stav, ne opětovné přimíchání původního snapshotu. **Nezahazovat produkční SQLite při denní aktualizaci:** uchovává i stav odstranění a nejvyšší přijatou revizi. `--reviewed-snapshot` dovoluje provozovateli výslovně určit jiný schválený soubor, nikoli obejít bootstrap marker existující databáze.

Feed se načítá jednou za běh stejným robots-aware HTTP klientem (HTTPS, časové odstupy, limity velikosti a opakování). Veřejné URL zdrojů zůstávají primární; URL přenosu se nevkládá do žádného veřejného výstupu. `lastChecked` a `lastSuccess` znamenají kontrolu přenosu, nikoli nové ověření pořadatele. `verifiedAt` každé akce je původní hodnota z podkladu.

## Autorita revizí a selhání

- Úspěšná validní revize nahrazuje množinu přijatých akcí; odebrané ID nebo celý prázdný seznam zůstává odebraný i při dalším běhu/výpadku.
- Síťový výpadek zachová poslední dobré záznamy a viditelně označí chybu. Při prvním výpadku se může použít schválený snapshot, ale nevymýšlí se úspěšná síťová kontrola.
- Neplatný záznam po změně se stáhne, ostatní bezpečně rozpoznané validní záznamy zůstávají. Duplicitní ID stáhne oba kandidáty. Review obsahuje jen kontrolovaný text a bezpečnou primární URL, nikoli neověřený název, extra pole nebo soukromé hodnoty.
- Neplatný kořen, soukromé extra pole na kořeni nebo starší revize stáhne celý redakční výběr do kontroly. Nejvyšší přijatý timestamp se nesníží. Stejný timestamp dovoluje jen identický logický obsah; oprava změněného feedu potřebuje novější `generatedAt` s časovým pásmem.
- Běžná provenience primárních polí používá původní datum důkazu a `NULL` hash nenačtené primární stránky. `reviewed_provenance` odděleně zaznamenává skutečný hash bajtů snapshotu/feedu, způsob přenosu, čas přenosu a soukromou URL. Žádný hash ani nové datum primárního ověření se nevyrábí.
- Databázová chyba je fatální, transakce se vrátí a spojení se zavře; nevydává se nový výstup nebo falešně úspěšné čerstvé ověření.

Kořen i položky mají uzavřenou množinu polí. Příchozí akce smějí mít přesně veřejná pole s krajem nebo bez kraje; bez kraje jej určuje pouze výslovná registrovaná vazba hostitele a obce. Žádné vstupní objekty se nemění. Kontrola soukromých řetězců kontroluje i percent-encoded hodnoty. HTML adaptéry si zachovávají striktní kontroly roku, místa, cen a vícečetných termínů.

## Limity, provoz a ověření

Výchozí limit běžného zdroje je dál 2 výpisy / 14 detailů. Konfigurace dovoluje nejvýše 4 / 40, validovaná před načítáním. Telč, Humpolec a Hranice mají 40 detailů; Jilemnice, Hořovice, Třeboň, Nejdek a Radotín 4 výpisy. Nezvyšuje se rozpočet ostatních zdrojů. Veřejné efektivní limity se generují z konfigurace. Podproces sběru v publisheru má 1800 s místo 600 s; plánovač, zámek a publikační Git ochrany se nemění.

Přenosné offline regresní příkazy:

```sh
python -m unittest discover -s tests -p test_reviewed_public.py -v
python -m unittest discover -s tests -p test_collection_budgets.py -v
python -m unittest discover -s tests -q
python scripts/collector.py --help
python scripts/publish_daily.py --check
```

Lifecycle testy používají skutečné čerstvé SQLite, přenosné veřejné fixtures, CLI i validátor: zachování všech 51 s původními hodnotami po opakovaném běhu; odstranění/výpadek; jednotlivé invalidní položky; soukromá pole; přesný rozsah obcí/hostitelů/geodat; duplicitní ID; starší a shodné revize; prázdný feed; oddělenou provenienci; fatální SQL a uvolnění zámku. Test budgetu nejprve reprodukoval oříznutí 40 položek na 14, nyní ověřuje přesně 4 listingové a 40 detailních požadavků a zachované legacy 2/14. Tyto offline testy nejsou vydávány za živé národní kolekce nebo publikaci; ty se provádějí odděleně nad produkční kopií databáze a cache.
