import tempfile,unittest
from pathlib import Path
from sync_guide import decide
class TestDecide(unittest.TestCase):
 def test_equal(self): self.assertEqual(decide('a','a','a'),'equal')
 def test_vault_change(self): self.assertEqual(decide('b','a','a'),'to_repo')
 def test_repo_change(self): self.assertEqual(decide('a','b','a'),'to_vault')
 def test_both_changed(self): self.assertEqual(decide('b','c','a'),'conflict')
 def test_no_base_conflict(self): self.assertEqual(decide('b','c',None),'conflict')
 def test_converged_change(self): self.assertEqual(decide('b','b','a'),'equal')
if __name__=='__main__':unittest.main()

class TestIntegration(unittest.TestCase):
 def test_both_directions_and_conflict(self):
  import contextlib,io,sys
  from unittest.mock import patch
  import sync_guide as s
  with tempfile.TemporaryDirectory() as d:
   base=Path(d);v=base/'vault';r=base/'repo';(v/'项目资料').mkdir(parents=True);(v/'工具').mkdir();(r/'docs/research').mkdir(parents=True)
   a=v/'项目资料'/s.NAME;b=r/'docs/research'/s.NAME;a.write_text('base');b.write_text('base')
   def run():
    with patch.object(s,'VAULT',v),patch.object(s,'REPO',r),patch.object(sys,'argv',['sync','--apply']),contextlib.redirect_stdout(io.StringIO()):return s.main()
   self.assertEqual(run(),0);a.write_text('vault change');self.assertEqual(run(),0);self.assertEqual(b.read_text(),'vault change')
   b.write_text('repo change');self.assertEqual(run(),0);self.assertEqual(a.read_text(),'repo change')
   a.write_text('one');b.write_text('two');self.assertEqual(run(),2);self.assertEqual(a.read_text(),'one');self.assertEqual(b.read_text(),'two')
