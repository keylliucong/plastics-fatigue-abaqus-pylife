import unittest
from sync_zotero import render_index
class SyncTests(unittest.TestCase):
 def test_deduplicates_and_links_existing_notes(self):
  rows=[{'key':'ABCD1234','title':'Paper','doi':'10.1/a','itemType':'journalArticle'},{'key':'ABCD1234','title':'Paper','doi':'10.1/a','itemType':'journalArticle'}]
  result=render_index(rows,{'ABCD1234'})
  self.assertEqual(result.count('[[ABCD1234|Paper]]'),1)
  self.assertIn('https://doi.org/10.1/a',result)
 def test_new_item_is_plain_text(self):
  self.assertNotIn('[[NEW12345',render_index([{'key':'NEW12345','title':'New','itemType':'journalArticle'}],set()))
if __name__=='__main__': unittest.main()

class TestNewNote(unittest.TestCase):
 def test_new_note_preserves_existing(self):
  import tempfile
  from pathlib import Path
  from sync_zotero import create_missing_notes
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d); old=folder/'ABCD1234.md';old.write_text('个人记录')
   result=create_missing_notes([{'key':'ABCD1234','title':'Old','itemType':'journalArticle'},{'key':'NEW12345','title':'New','doi':'10.1/x','itemType':'journalArticle'}],folder)
   self.assertEqual(old.read_text(),'个人记录'); self.assertEqual(result,{'NEW12345'})
   self.assertIn('10.1/x',(folder/'New.md').read_text())
