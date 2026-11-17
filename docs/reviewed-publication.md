# Redakčně ověřené akce a jejich přenos

`data/reviewed-events.json` je verzovaný veřejný výběr faktů s původními daty ověření. Jeho kanonický přenosový zdroj je `https://raw.githubusercontent.com/romanzdk/advent-cesko-pilot/main/data/reviewed-events.json`. Neobsahuje osobní kalendář, účastníky ani neveřejný výzkumný stav. Přenos nesmí záviset na dostupnosti jiného webu nebo soukromého repozitáře.

- Před změnou načtěte aktuální `main`, skutečnou veřejnou projekci a odpovídající místní databázi. Čerstvý Git není důkazem úplné databáze. Nesoulad vyžaduje zastavení publikace, ne přegenerování menšího katalogu.
- Nový veřejný podnět nejdřív porovnejte podle primární URL, dne, skutečné obce, místa a programu s celým katalogem. Jiný výzkumný identifikátor není nová akce. Zachovejte existující kanonické ID, vlastníka zdroje a původní ověření nedotčených položek.
- Každý záznam musí mít jedinou schválenou vazbu na zdroj. Opravu existujícího obecního detailu uložte jako přesné obsahově vázané rozhodnutí tohoto adaptéru, nikoli jako druhý redakční import stejné URL. Samostatný redakční PDF podklad může mít vlastní přesnou vazbu bez překrytí s obecními HTML detaily.
- Ověřené nové hodiny pocházejí z aktuálních veřejných podkladů. Historický celodenní zápis v soukromém kalendářním archivu je nesmí přepsat; archiv se kvůli webu neupravuje. Rozpory v místě a hodinách musí zůstat výslovné. Neznámé souřadnice jsou `null`.
- Novou revizi celého redakčního výběru sestavte z aktuálních schválených záznamů, nikoli z historické výchozí kopie. Bez výslovného a doloženého důvodu nemažte žádnou stávající akci. Změna revize potřebuje nový čas `generatedAt`, nikoli nové datum ověření u všech původních akcí.
- Otestujte přesné vazby a veřejný validátor. Dva skutečné přenosy stejné zmrazené revize musí dát stejné významové výsledky a zachovat netýkané záznamy. `--reviewed-only` neověřuje znovu pořadatelské weby a nemá spouštět celostátní sběr. Změna faktů živého adaptéru vyžaduje samostatné ověření dotčeného zdroje.
- Po schváleném sloučení aktualizujte odpovídající databázi a privátní nastavení přenosu pouze pod existujícím publikačním zámkem s přesnou výchozí verzí a zálohou. Neměňte žádné cizí úpravy, webové rozhraní ani oprávnění kalendáře. Ověřte odpovídající nasazení, všechny veřejné projekce a konkrétní nové či opravené akce na skutečném webu.

Úspěšný návrat publisheru s uchovanými starými daty není důkazem nového importu: zkontrolujte `status`, `lastSuccess` a `lastError` dotčených redakčních zdrojů i přítomnost očekávaných položek.
