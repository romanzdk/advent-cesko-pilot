# Provoz a ověření

Tento dokument je určený ke správě autorizované pracovní kopie projektu. Veřejné zpřístupnění příkazů neuděluje právo provozovat vlastní kopii; podmínky jsou v [LICENSE](../LICENSE).

## Co kde běží

- Python sběrač a publisher běží na lokálním serveru. Produkční publisher používá POSIX zámek `fcntl`, Git a autentizovaný GitHub CLI `gh`.
- Hermes pouze plánuje spuštění skriptu v režimu `no_agent`. K samotnému sběru nejsou potřeba LLM ani API klíče pořadatelů.
- GitHub Actions provede kontroly a nasadí pouze `site/` na GitHub Pages.
- Návštěvníkův prohlížeč načítá statické soubory a mapové dlaždice. Nepřistupuje k SQLite ani k lokálnímu serveru.

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
node --test tests-ui/helpers.test.mjs tests-ui/pilot.test.mjs
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

Po rozšíření z 12. listopadu 2026 registr zahrnuje 12 zdrojů v šesti krajích. Validátor odvozuje přesná ID a počet zdrojů, jejich kraje, obce i přiřazení zdrojových URL z `data/sources.json`; pro izolované testy lze `validate_directory(path, registry=...)` předat jiný registr. Rozhraní odvozuje souhrn pokrytí z veřejných dat. Přidání kraje proto nevyžaduje přepsat pevný počet, ale stále vyžaduje zdrojové a geografické ověření.

Šest nových zdrojů používá `allowed_venues`: seznam přesně ověřených míst v obci, porovnávaný po normalizaci NFKC, mezer a velikosti písmen. Nové či změněné místo čeká na kontrolu; seznam není obecný geokodér ani oprávnění přiřadit sousední obec ke zdroji. Podklady pro přidání místa nejprve ověřte u pořadatele. Automatické objevování nových akcí na již ověřených místech zůstává funkční.

Nový zdroj musí mít ověřenou lokalitu, současný rok v obsahu, povolené automatické načítání a regresní podklad pro jeho formát. Každé rozšíření projde skutečným sběrem a opakovaným průchodem bez nových duplicit. Rozsah se na webu označuje jako výběr, nikoli úplný krajský katalog.

## Dokumentační obrázky

`docs/assets/desktop.png` a `mobile.png` jsou skutečné screenshoty veřejného webu z 12. listopadu 2026. Desktop ukazuje výchozí přehled, mobil filtr rozsvícení stromů. Nejde o fixture server ani upravená ukázková data.

`docs/assets/architecture.png` je vykreslené schéma z [architecture.html](architecture.html). HTML obsahuje inline SVG, funguje bez externích knihoven a lze ho otevřít samostatně. Obrázky nejsou součástí Pages artefaktu, protože nasazení nadále publikuje jen `site/`.
