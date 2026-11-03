"""Pure visibility ordering tests; these do not import or simulate NX."""
import unittest
import json

from renovierung.m01 import display


class VisibilityOrderTests(unittest.TestCase):
    def order(self, parents, states):
        function = getattr(display, 'visibility_order', None)
        self.assertTrue(callable(function), 'Missing pure visibility_order helper')
        return function(parents, states)

    def test_ancestors_always_precede_descendants_for_native_cascades(self):
        parents = {'CONSTRUCTION': 'MASTER', 'SECTION': 'CONSTRUCTION',
                   'FIELD': 'SECTION', 'CUT_SOIL': 'FIELD', 'RESERVE': 'FIELD',
                   'HOUSE': 'MASTER', 'ROOMS': 'HOUSE', 'ROOM': 'ROOMS',
                   'ENVIRONMENT': 'MASTER', 'TERRAIN': 'ENVIRONMENT'}
        states = {key: key in {'FIELD', 'RESERVE', 'ROOMS', 'TERRAIN'} for key in parents}
        order = self.order(parents, states)
        self.assertEqual(set(order), set(parents))
        self.assertEqual(len(order), len(parents))
        for child, parent in [('CUT_SOIL', 'FIELD'), ('RESERVE', 'FIELD'), ('ROOM', 'ROOMS')]:
            self.assertLess(order.index(parent), order.index(child))

    def test_hidden_ancestors_expand_and_selected_field_restores_role_defaults(self):
        function = getattr(display, 'effective_visibility', None)
        self.assertTrue(callable(function), 'Missing effective_visibility helper')
        parents = {'SECTION': 'MASTER', 'FIELD': 'SECTION', 'OTHER_FIELD': 'SECTION',
                   'CUT_SOIL': 'FIELD', 'MAIN': 'FIELD', 'EXCAVATION': 'FIELD', 'RESERVE': 'FIELD',
                   'OTHER_CUT': 'OTHER_FIELD', 'ROOMS': 'MASTER', 'ROOM': 'ROOMS'}
        states = {key: key in {'FIELD', 'OTHER_FIELD', 'EXCAVATION', 'RESERVE', 'ROOMS'}
                  for key in parents}
        original = dict(states)
        actual = function(parents, states)
        self.assertEqual(actual, {key: key != 'SECTION' for key in parents})
        states['FIELD'] = False
        selected = function(parents, states)
        for key in ('FIELD', 'CUT_SOIL', 'MAIN'):
            self.assertFalse(selected[key], key)
        for key in ('OTHER_FIELD', 'OTHER_CUT', 'EXCAVATION', 'RESERVE', 'ROOMS', 'ROOM'):
            self.assertTrue(selected[key], key)
        states['FIELD'] = True
        self.assertEqual(states, original)
        self.assertEqual(function(parents, states), actual)

    def test_invalid_requests_fail_before_an_order_is_returned(self):
        cases = [({'FIELD': 'MASTER'}, {}),
                 ({'FIELD': 'MASTER'}, {'FIELD': False, 'OTHER': True}),
                 ({'FIELD': 'MISSING'}, {'FIELD': False}),
                 ({'FIELD': 'FIELD'}, {'FIELD': True}),
                 ({'A': 'B', 'B': 'A'}, {'A': False, 'B': True}),
                 ({'FIELD': 'MASTER'}, {'FIELD': 1})]
        for parents, states in cases:
            with self.subTest(parents=parents, states=states):
                with self.assertRaises(ValueError):
                    self.order(parents, states)

    def test_attribute_json_chunks_round_trip(self):
        function = getattr(display, 'attribute_chunks', None)
        self.assertTrue(callable(function), 'Missing JSON attribute serialization helper')
        for value in ['FIELD_PS01-F01', False, {'original_room_name': 'Küche', 'source': 'x'*2500}]:
            with self.subTest(value_type=type(value).__name__):
                chunks = function('M01_TEST', value)
                self.assertEqual(json.loads(''.join(text for _, text in chunks)), value)
                if len(chunks) == 1:
                    self.assertEqual(chunks[0][0], 'M01_TEST')
                else:
                    self.assertEqual([key for key, _ in chunks],
                                     ['M01_TEST_%03d' % i for i in range(len(chunks))])
                    self.assertTrue(all(0 < len(text) <= 900 for _, text in chunks))
                self.assertTrue(all(text.isascii() for _, text in chunks))


if __name__ == '__main__':
    unittest.main()
