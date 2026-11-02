"""Reject obsolete CAD input and test conservative exclusion geometry."""
from pathlib import Path
import importlib.util,subprocess,sys,tempfile,unittest
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('b',root/'tools/bambu_3mf.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
class Contract(unittest.TestCase):
    def test_hull_exclusion(self):
        diamond=[(0,1,0),(1,0,0),(2,1,0),(1,2,0)]
        self.assertFalse(b.hull_intersects_rectangle(diamond,[1.8,1.8,2,2]))
        self.assertTrue(b.hull_intersects_rectangle(diamond,[.9,.9,1.1,1.1]))
        self.assertTrue(b.hull_intersects_rectangle(diamond,[-1,-1,3,3]))
        self.assertTrue(b.hull_intersects_rectangle(diamond,[.9,-1,1.1,3]))
    def test_reject_p4(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=subprocess.run([sys.executable,str(root/'build.py'),'--cad',str(root.parent/'p4-uniform-vents/out'),'--out',str(Path(tmp)/'out')],capture_output=True,text=True)
            self.assertNotEqual(run.returncode,0)
            self.assertIn('Expected P5 CAD output',run.stderr)
    def test_archive_repeatable(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'a.3mf';c=Path(tmp)/'c.3mf'
            b.write_archive({'b':b'2','a':b'1'},a)
            b.write_archive({'a':b'1','b':b'2'},c)
            self.assertEqual(a.read_bytes(),c.read_bytes())
if __name__=='__main__':unittest.main()
