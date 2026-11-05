import unittest
from copy import deepcopy

from renovierung.m01.pile_transfer import validate_pile_locations


class PileLocationsTests(unittest.TestCase):
    def setUp(self):
        roles=('pile_main','pile_reserve')
        self.field={'id':'PS01-F01','native':True,
                    'display_stockpile':{r:{'bbox_mm':[0,0,0,4000,5000,2000]} for r in roles},
                    'measurements':{r:{'body_count':1} for r in roles},
                    'k02_pile_measurements':{r:{'body_count':1} for r in roles}}
        self.actual={self.field['id']:{r:{'bbox_mm':[0,0,0,4000,5000,2000],'body_count':1} for r in roles}}
        self.actual[self.field['id']]['historical_hidden']={r:1 for r in roles}

    def test_actual_new_location_and_archived_original(self):
        validate_pile_locations({'fields':[self.field]}, self.actual)

    def test_same_volume_at_old_location_does_not_pass(self):
        bad=deepcopy(self.actual)
        bad['PS01-F01']['pile_main']['bbox_mm'][1] -= 6500
        with self.assertRaises(ValueError):
            validate_pile_locations({'fields':[self.field]},bad)

    def test_missing_hidden_original_does_not_pass(self):
        self.actual['PS01-F01']['historical_hidden']['pile_reserve']=0
        with self.assertRaises(ValueError):
            validate_pile_locations({'fields':[self.field]},self.actual)
