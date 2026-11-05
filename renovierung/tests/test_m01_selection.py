"""Selection routing at a mocked UI boundary, without native CAD claims."""
import types
import unittest
from unittest.mock import Mock, patch

from renovierung.m01.select_state import selected_field


class SelectionTests(unittest.TestCase):
    def resolve(self, native, catalog):
        component = types.SimpleNamespace(Tag=17)
        master = Mock()
        master.HasUserAttribute.return_value = catalog is not None
        manager = Mock()
        manager.GetNumSelectedObjects.return_value = 1
        manager.GetSelectedTaggedObject.return_value = component
        nx = types.SimpleNamespace(
            UI=types.SimpleNamespace(GetUI=lambda: types.SimpleNamespace(SelectionManager=manager)),
            NXObject=types.SimpleNamespace(AttributeType=types.SimpleNamespace(String=1)))
        attributes = {
            'M01_NODE_ID': 'FIELD_PS11-F04', 'M01_KIND': 'field',
            'M01_FIELD_ID': 'PS11-F04', 'M01_FIELD_NATIVE': native,
            'M01_FIELD_METADATA': {'sector_id': 'PS11'}, 'M01_STATE_CATALOG': catalog}
        with patch.dict('sys.modules', {'NXOpen': nx}), \
                patch('renovierung.m01.display.components', return_value={'FIELD_PS11-F04': component}), \
                patch('renovierung.m01.display.read_attribute', side_effect=lambda obj, key: attributes[key]):
            return selected_field(master)

    def test_diagnostic_with_saved_state_selects_its_own_field(self):
        self.assertEqual(self.resolve(False, {'PS11-F04': 'M01_PS11_F04'}), 'PS11-F04')

    def test_register_without_saved_state_keeps_section_fallback(self):
        self.assertEqual(self.resolve(False, {'PS11': 'M01_PS11'}), 'PS11')

    def test_legacy_native_selection_still_selects_field(self):
        self.assertEqual(self.resolve(True, None), 'PS11-F04')
