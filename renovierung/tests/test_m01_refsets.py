"""Reference-member record validation only; no NX imports or simulations."""
import unittest

from renovierung.m01 import nx_journal


class ReferenceMembersTests(unittest.TestCase):
    def validate(self, expected, members):
        function = getattr(nx_journal, 'validate_refset_members', None)
        self.assertTrue(callable(function), 'Missing reference-member validator')
        return function(expected, members)

    def test_exact_bodies_and_associated_facets_are_accepted(self):
        expected = {1: 'K02_CUT_SOIL_00', 2: 'K02_CUT_SOIL_01'}
        members = [{'kind': 'body', 'tag': 1}, {'kind': 'body', 'tag': 2},
                   {'kind': 'facet', 'tag': 10, 'associated_loaded': True, 'associated_tag': 1}]
        self.assertEqual(self.validate(expected, members), ['K02_CUT_SOIL_00'])
        self.assertEqual(self.validate(expected, members[:2]), [])

    def test_wrong_missing_duplicate_and_orphan_members_fail(self):
        body = {'kind': 'body', 'tag': 1}
        bad = [[], [{'kind': 'body', 'tag': 2}], [body, body],
               [body, {'kind': 'other', 'tag': 2}],
               [body, {'kind': 'facet', 'tag': 10, 'associated_loaded': False, 'associated_tag': 1}],
               [body, {'kind': 'facet', 'tag': 10, 'associated_loaded': True, 'associated_tag': None}],
               [body, {'kind': 'facet', 'tag': 10, 'associated_loaded': True, 'associated_tag': 2}]]
        for members in bad:
            with self.subTest(members=members):
                with self.assertRaises(ValueError):
                    self.validate({1: 'K02_CUT_SOIL_00'}, members)


if __name__ == '__main__':
    unittest.main()
