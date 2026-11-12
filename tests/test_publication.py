import copy,importlib.util,json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class PublicValidationTests(unittest.TestCase):
 def test_projection_is_strict_and_private_metadata_is_rejected(self):
  path=ROOT/'scripts/validate_public.py'
  self.assertTrue(path.exists(),'Public validation is missing')
  spec=importlib.util.spec_from_file_location('validate_public',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  e=dict(id='e-test',title='Vánoční trhy',town='Plasy',region='Plzeňský kraj',venue=None,date='2026-11-28',endDate=None,startTime='16:30',endTime=None,category='trhy',price=None,registration=None,registrationUrl=None,description='Vánoční trhy',notes=[],audience='všichni',status='confirmed',verifiedAt='2026-11-12T12:00:00+00:00',sourceUrl='https://www.plasy.cz/akce',location={'lat':49.9341107,'lon':13.3889549,'precision':'town','label':'Plasy — orientační poloha','sourceUrl':'https://www.openstreetmap.org/relation/439746'})
  data=dict(schemaVersion=1,season=2026,generatedAt=e['verifiedAt'],region='Česko – pilot tří krajů',events=[e])
  self.assertTrue(m.validate(data))
  for field,value in [('attendees',[]),('date','2025-11-28'),('sourceUrl','https://name:pass@www.plasy.cz/akce'),('description','owner@example.invalid'),('startTime','25:00'),('location',{'lat':1,'lon':1,'precision':'town','label':'bad','sourceUrl':'https://www.openstreetmap.org/relation/1'})]:
   bad=copy.deepcopy(data);bad['events'][0][field]=value
   with self.subTest(field=field),self.assertRaises(ValueError):m.validate(bad)
  bad=copy.deepcopy(data);bad['calendar_id']='secret'
  with self.assertRaises(ValueError):m.validate(bad)
