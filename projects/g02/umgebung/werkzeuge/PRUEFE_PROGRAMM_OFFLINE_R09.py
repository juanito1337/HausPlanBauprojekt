"""Programmlogik offline testen. Nicht in NX starten; doppelte Test-IDs nicht zaehlen."""
from pathlib import Path
import sys,unittest
BASE=Path(__file__).absolute().parents[1]
sys.path.insert(0,str(BASE))
def unique_suite(suite):
    seen=set();out=unittest.TestSuite()
    def add(node):
        if isinstance(node,unittest.TestSuite):
            for child in node:add(child)
        elif node.id() not in seen:
            seen.add(node.id());out.addTest(node)
    add(suite)
    return out
if __name__=='__main__':
    suite=unique_suite(unittest.defaultTestLoader.discover(str(BASE/'tests')))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
