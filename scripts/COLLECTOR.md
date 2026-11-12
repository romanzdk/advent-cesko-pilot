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

Sběrač načte nejvýše dvě stránky výpisu a čtrnáct detailních URL na zdroj; zdroj může limit detailů dále snížit. Sleduje skutečné odkazy na stejném hostiteli, filtruje je podle registru a sezonního popisku. Nové odkazy mají přednost před bootstrap URL; známé uložené detaily se znovu kontrolují v rámci stejného limitu. Zachovává původní percent-encoding adres.

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

Rok se neodvozuje z URL, patičky ani data publikace článku. Chybějící či rozporný údaj znamená ruční kontrolu, datum mimo sledované období známé vyřazení. Půlnoc používaná CMS jako výchozí hodina zůstává neznámým časem. Krajní termíny vícedenních akcí nenahrazují otevírací dobu.

Přesné geografické přiřazení URL je podmíněné shodou zdroje, normalizovaného pole místa a ověřeného data. Místní části Plas proto používají vlastní orientační polohy. Změna podkladů přiřazení zneplatní a položka se vrátí do kontroly; nejde o obecný automatický geokodér.

Nových šest zdrojů v Berouně, Hořovicích, Soběslavi, Třeboni, Telči a Humpolci má navíc `allowed_venues`: přesně ověřené názvy míst v obci. Porovnání normalizuje NFKC, mezery a velikost písmen, nikoli význam nebo adresu. Neznámé místo zůstává k ověření, aby regionální kalendář nevydával akce sousedních obcí za místní. Toto omezení nebrání objevování nových akcí na již ověřeném místě.

## Identita, změny a selhání

SQLite uchovává stabilní identifikátor odvozený z přesné zdrojové URL a otisk věcného obsahu bez času kontroly. Rozlišuje nové, změněné a nezměněné položky. Původ důležitých polí se zapisuje se zdrojem a pozorováním; pro dodatečný podpůrný zdroj se nevymýšlí hash nezachycené stránky.

Při chybě načtení zůstávají poslední dobré události. Při nově načtené nejednoznačné revizi se stará veřejná položka stáhne do kontroly. Odstranění stránky samo o sobě není zrušením akce. Zájezdy a termíny mimo rozsah se evidují jako vyřazení, odděleně od nevyřešených kandidátů.

Deduplikace porovnává obec, místo, datum, název a začátek. Záznamy bez uvedeného místa se neslučují jen podle názvu. Zdrojové počty mohou před deduplikací převyšovat počet veřejně publikovaných událostí.

## Testování a omezení

`--offline-fixtures MANIFEST.json` mapuje přesné URL na soubory relativně k manifestu. Při chybějícím podkladu nevzniká síťový fallback. Čistý checkout obsahuje malé faktické fragmenty; původní úplné zachycené stránky zůstávají soukromé. Testy a jejich podklady nejsou vydávané za úspěšný živý sběr.

Projekt nemá obecné OCR plakátů, import libovolných PDF, Facebook, přihlašování, odvozování termínů z RSS publikačních dat ani AI fallback. Omezené procházení nikdy neopravňuje tvrdit úplnost regionu; `coverage.json` výslovně uvádí `complete: false`.
