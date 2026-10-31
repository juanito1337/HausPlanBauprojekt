"""Tests nur für Repository-Integrität/Verpackung; kein NX und keine Statik."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest

ROOT=Path(__file__).absolute().parents[1]
sys.path.insert(0,str(ROOT))
try:
    from tools import repo_support as rs
except ImportError:
    rs=None

class RepoToolTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(rs, 'tools/repo_support.py ist noch nicht implementiert')
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
    def test_digest(self):
        p=self.root/'a';p.write_bytes(b'abc')
        self.assertEqual(rs.digest(p),hashlib.sha256(b'abc').hexdigest())
    def test_member_normal(self):
        self.assertEqual(rs.member_path(self.root,'a/b.txt'),self.root/'a/b.txt')
    def test_member_parent(self):
        with self.assertRaises(ValueError):rs.member_path(self.root,'../escape')
    def test_member_absolute(self):
        with self.assertRaises(ValueError):rs.member_path(self.root,'/escape')
    def test_member_windows(self):
        with self.assertRaises(ValueError):rs.member_path(self.root,'C:/escape')
    def test_member_backslash(self):
        with self.assertRaises(ValueError):rs.member_path(self.root,r'a\b')
    def test_member_empty(self):
        with self.assertRaises(ValueError):rs.member_path(self.root,'')
    def test_member_symlink(self):
        other=self.root/'elsewhere';other.mkdir();link=self.root/'link'
        try:link.symlink_to(other,target_is_directory=True)
        except (OSError,NotImplementedError):self.skipTest('Symlinks nicht erlaubt')
        with self.assertRaises(ValueError):rs.member_path(self.root,'link/file')
    def test_manifest_ok(self):
        p=self.root/'a';p.write_bytes(b'abc')
        self.assertEqual(rs.check_files(self.root,{'a':rs.digest(p)}),[])
    def test_manifest_modified(self):
        (self.root/'a').write_bytes(b'changed')
        errors=rs.check_files(self.root,{'a':hashlib.sha256(b'abc').hexdigest()})
        self.assertEqual(errors[0]['kind'],'changed')
    def test_manifest_missing(self):
        errors=rs.check_files(self.root,{'a':'0'*64})
        self.assertEqual(errors[0]['kind'],'missing')
    def test_manifest_bad_digest(self):
        with self.assertRaises(ValueError):rs.check_files(self.root,{'a':'bad'})
    def test_manifest_case_collision(self):
        with self.assertRaises(ValueError):rs.check_files(self.root,{'A':'0'*64,'a':'1'*64})
    def test_archive_roundtrip(self):
        (self.root/'a.txt').write_text('ä\n',encoding='utf-8')
        out=self.root.parent/(self.root.name+'.zip');self.addCleanup(lambda:out.unlink(missing_ok=True))
        result=rs.build_archive(self.root,['a.txt'],out,'Example')
        self.assertEqual(result['files'],1);self.assertTrue(result['crc_passed'])
        import zipfile
        with zipfile.ZipFile(out) as z:self.assertEqual(z.read('Example/a.txt'),(self.root/'a.txt').read_bytes())
    def test_archive_refuses_overwrite(self):
        out=self.root.parent/(self.root.name+'.zip');out.write_bytes(b'original')
        self.addCleanup(lambda:out.unlink(missing_ok=True))
        with self.assertRaises(FileExistsError):rs.build_archive(self.root,[],out,'Example')
        self.assertEqual(out.read_bytes(),b'original')
    def test_archive_refuses_inside_repository(self):
        with self.assertRaises(ValueError):rs.build_archive(self.root,[],self.root/'out.zip','Example')
    def test_archive_refuses_git_metadata(self):
        with self.assertRaises(ValueError):rs.build_archive(self.root,['.git/config'],self.root.parent/'other.zip','Example')
    def test_archive_refuses_duplicate(self):
        with self.assertRaises(ValueError):rs.build_archive(self.root,['a','a'],self.root.parent/'other.zip','Example')
    def test_archive_refuses_missing_input(self):
        with self.assertRaises(FileNotFoundError):rs.build_archive(self.root,['absent'],self.root.parent/'other.zip','Example')
    def test_python_syntax_310(self):
        p=self.root/'x.py';p.write_text('def f(x: int) -> int:\n    return x\n',encoding='utf-8')
        self.assertEqual(rs.check_python_syntax(self.root,['x.py']),[])
    def test_bad_syntax(self):
        (self.root/'x.py').write_text('def x(:',encoding='utf-8')
        self.assertEqual(len(rs.check_python_syntax(self.root,['x.py'])),1)
    def test_extract_json_assignment(self):
        self.assertEqual(rs.extract_json_assignment('const P={"a":[1,2]}; draw();'), {'a':[1,2]})
    def test_extract_rejects_javascript(self):
        with self.assertRaises(ValueError):rs.extract_json_assignment('const P=fetch("secret");')
    def test_extract_rejects_ambiguous_assignment(self):
        with self.assertRaises(ValueError):rs.extract_json_assignment('const P={}; const P={};')
    def test_extract_requires_assignment(self):
        with self.assertRaises(ValueError):rs.extract_json_assignment('<html>missing</html>')
    def test_extract_requires_terminator(self):
        with self.assertRaises(ValueError):rs.extract_json_assignment('const P={} + execute();')
    def test_baseline_import_manifest_exists(self):
        self.assertTrue((ROOT/'provenance/IMPORT_MANIFEST.json').is_file())
    def test_k01_is_documents_only(self):
        folder=ROOT/'renovierung/k01_unterlagen'
        self.assertTrue((folder/'BAUABSCHNITTE_K01.csv').is_file())
        self.assertEqual(list(folder.rglob('*.py')),[])
        self.assertEqual(list(folder.rglob('*.step')),[])

if __name__=='__main__':unittest.main(verbosity=2)
