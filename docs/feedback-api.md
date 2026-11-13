# Návrhy akcí a hlášení chyb

Tento dokument popisuje veřejný postup a obecné bezpečnostní hranice. Konfigurace konkrétního serveru, interní síť, umístění soukromého stavu a přihlašovací údaje do veřejné dokumentace nepatří.

## Jak podat návrh nebo opravu

- **Nová akce:** na [Kam na advent](https://kamnaadvent.cz/#feedback) rozbalte „Chybí vám akce nebo obec?“ a vyplňte plný formulář. Potřebujeme název, obec, veřejný zdroj a datum, případně výslovné označení neznámého data. Místo, časy, kraj, kategorie, cena, rezervace, publikum, popis a poznámky pomáhají s ověřením.
- **Rychlý tip:** pokud nemáte všechny údaje, přepněte formulář na rychlý tip. Stačí obec, odkaz na zdroj nebo popis; neznámé údaje nevymýšlejte.
- **Chyba u existující akce:** na její kartě zvolte „Nahlásit chybu“, vyberte typ problému a popište opravu. Kontext se doplní podle aktuálního katalogu, můžete přidat veřejný zdroj.

Pro odeslání přes web **nepotřebujete účet na GitHubu**. Před odesláním je nutný výslovný souhlas se zveřejněním obsahu na veřejném GitHubu. Samotné používání webu žádný návrh neposílá.

## Co následuje po odeslání

**Formulář → kontrola vstupu → trvalá fronta → veřejné hlášení na GitHubu → redakční kontrola → případná změna mapy.**

1. Server ověří tvar podání, povinná pole, souhlas a základní ochrany proti zneužití. Oprava musí odkazovat na existující akci.
2. Platné podání se nejdřív uloží do fronty. **Přijetí do fronty ještě nepotvrzuje zveřejnění na GitHubu.**
3. Oddělený neveřejný odesílatel vytvoří hlášení v pevném repozitáři. Potvrzený odkaz formulář zobrazí až po zpětném ověření konkrétního hlášení a jeho obsahu.
4. Podnět zůstává neověřeným návrhem. Před zařazením nebo opravou se kontroluje pořadatel, rok, datum, skutečné místo a případné duplicity. **Podání samo nemění mapu, zdroje sběrače, kalendáře ani pozvánky.**

[Veřejná hlášení](https://github.com/romanzdk/advent-cesko-pilot/issues?q=is%3Aissue) pomáhají předcházet duplicitám. Panel na webu ukazuje jen omezený nedávný výběr otevřených i uzavřených podnětů; není to úplná kontrola celé historie. U podání není slíbená konkrétní doba vyřízení.

## Přijetí, chyba a opakování

- **Čeká ve frontě:** podání bylo přijato, ale zveřejnění ještě není potvrzené.
- **Nejistý stav:** odpověď mohla vypadnout po přijetí. Nejde o důkaz, že podání nedorazilo.
- **Zveřejněno:** existuje zpětně ověřený odkaz na konkrétní hlášení na GitHubu; nejde ještě o schválení do mapy.
- **Odmítnutý vstup:** opravte uvedené pole nebo chybějící souhlas podle zprávy formuláře.

Po přijetí nebo nejisté odpovědi použijte ověření stavu, které zachovává identitu původního podání. Nevytvářejte další kopii jen proto, že odpověď trvá. Ruční [návrh přímo na GitHubu](https://github.com/romanzdk/advent-cesko-pilot/issues/new?template=tip.md) je záloha před přijetím; vyžaduje vlastní účet a konečné potvrzení na GitHubu. Formulář tuto zálohu po přijetí či nejednoznačném odeslání blokuje kvůli duplicitám.

## Soukromí a obsah

**Obsah podání bude veřejný.** Nevkládejte osobní kontakty, soukromé adresy, neveřejné odkazy ani jiné citlivé údaje. Absence přihlášení není příslib úplné síťové anonymity a uzavření hlášení jeho obsah samo neodstraní.

- Formulář nevyžaduje jméno, e-mail ani přístup k poloze a nepřijímá nahrávané soubory.
- Zdrojové a rezervační odkazy se při příjmu **nenačítají**. Kontrola jejich tvaru nepotvrzuje bezpečnost nebo pravdivost obsahu cílové stránky.
- Zadání veřejného zdroje nenahrazuje rezervaci ani nákup vstupenky.
- Volný text přesto může obsahovat osobní údaje. Upozornění, souhlas a technická validace nenahrazují redakční kontrolu.
- Přijímací služba neukládá klientskou IP adresu ani předanou hlavičku X-Forwarded-For do fronty; tento výrok se nevztahuje na případné provozní záznamy nezávislých síťových poskytovatelů.

## Obecné bezpečnostní hranice

- Veřejný příjem nemá GitHub přihlašovací údaje. Oddělený neveřejný odesílatel může zveřejňovat jen do pevně určeného repozitáře a nemá veřejné přijímací rozhraní.
- V prohlížeči není GitHub token pro zápis. Veřejné podněty nejsou příkazy, kód ani automatická konfigurace sběrače.
- Vstup má uzavřenou sadu polí, omezené délky, kontrolu dat/časů, výslovný souhlas a základní ochranu proti opakování a nadměrnému množství podání.
- Kontrola povoleného webového původu pomáhá v prohlížeči, ale **není ověřením člověka ani silnou ochranou proti botům**. Základní limity mohou být vyčerpány; moderace a neveřejný provozní dohled jsou nadále potřeba.
- Opakování přijatého podání nezakládá další hlášení. Po nejednoznačném zápisu odesílatel ověřuje původní pokus, nikoli nové vytvoření naslepo.
- Kontrola dostupnosti příjmu sama nepotvrzuje dostupnost odesílatele nebo GitHubu.

Veřejný postup a tyto hranice lze popsat otevřeně. Ochrana nesmí záviset na utajení principu fungování; konkrétní konfigurace infrastruktury a přihlašovací materiál se ale uchovávají odděleně a neveřejně.

## Základ veřejného rozhraní a ověření

Rozhraní podporuje návrh akce, rychlý tip a opravu. Prohlížeč získá jednorázový ověřovací údaj, odešle podání s vlastním náhodným identifikátorem a následně zjišťuje stav stejného podání. Stavové odpovědi nevracejí odeslaná pole ani interní cesty. Přesná implementace veřejného protokolu je v kódu; nejde o obecnou službu pro libovolné GitHub zápisy.

Izolované testy ověřují validaci, skutečnou dočasnou databázi, HTTP hranice, opakování, obnovu po přerušení a bezpečné vykreslení. Simulované odpovědi nepotvrzují živé doručení: to se ověřuje samostatně skutečným označeným technickým podáním, přesným přečtením výsledného hlášení a následným uzavřením testu. Konkrétní nasazení a obnovovací postupy patří do neveřejných provozních poznámek.
