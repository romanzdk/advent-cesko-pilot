# Six-source expansion parser regressions

`verified-fragments.json` contains 17 minimal semantic HTML fragments extracted
from the verified primary captures, plus curated expected source facts. Each case
records its public source URL and exact per-source venue allowlist. These are
portable parser fixtures, not full page snapshots; no private capture paths,
research metadata, scripts, maps, or organizer contact blocks are required.

Coverage: Beroun 3, Hořovice 2, Soběslav 3 (Galileo); Třeboň 3 (`itrebon`);
Telč 3 (`telc`); Humpolec 3 (`humpolec`). The 12 December Třeboň event retains
an unknown start time: the CMS's 00:00 is not a confirmed midnight opening.

The three standalone HTML files expose each new CMS's relevant DOM shape.
Their main event fields are factual excerpts from the source URL in the comment.
The Telč sidebar is deliberately synthetic boundary-test noise, not another
verified event. Tests mutate fragments to model missing years, conflicting dates,
unknown venues, midnight placeholders, and multiple distinct occurrences.

Run offline:

```sh
python -m unittest discover -s tests -p test_expansion_adapters.py -v
```

Limits: these adapters only recognize the inspected semantic layouts. Telč and
Humpolec multi-date/multi-occurrence details remain in review; they are not split
or guessed. Venue allowlists use NFKC, whitespace normalization and casefold only;
unknown venues require a new explicit verification. Common price extraction is
unchanged and does not claim to capture every price/membership variant.
