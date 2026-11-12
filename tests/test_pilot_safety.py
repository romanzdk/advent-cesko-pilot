import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('pilot_collector',ROOT/'scripts/collector.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
SOURCE={'town':'Kuřim','region':'Jihomoravský kraj','adapter':'drupal'}
WINDOW={'from':'2026-11-20','through':'2026-12-24'}
class SafetyTests(unittest.TestCase):
 def test_without_reservation_is_not_a_mandatory_booking(self):
  html='<main><h1>Vánoční tvoření</h1><time datetime="2026-12-10T17:00:00+01:00"></time><p>Vstup bez rezervace.</p></main>'
  e=c.parse_event(html,SOURCE,'https://www.kulturakurim.cz/akce-tvoreni',WINDOW)
  self.assertIsNone(e['registration'])

 def test_invalid_clock_cannot_be_silently_replaced_by_end_time(self):
  source=dict(SOURCE,adapter='galileo')
  html='<h1>Vánoční trhy</h1><div class="event-detail"><h2 class="action-date">5. 12. 2026 29:00 – 18:00</h2><h2 class="venue">Kuřim</h2></div>'
  with self.assertRaises(c.Review): c.parse_event(html,source,'https://www.kulturakurim.cz/akce-trhy',WINDOW)

 def test_coach_trip_is_not_misrepresented_as_a_local_market(self):
  html='<main><h1>Zájezd: vánoční trhy Karlovy Vary</h1><time datetime="2026-12-10T07:00:00+01:00"></time><div class="field--name-field-event-place">Kulturní dům Kuřim</div></main>'
  with self.assertRaises(c.Review): c.parse_event(html,SOURCE,'https://www.kulturakurim.cz/akce-zajezd',WINDOW)
