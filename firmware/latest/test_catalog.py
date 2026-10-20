import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('hub',Path(__file__).with_name('build.py'));hub=importlib.util.module_from_spec(spec);spec.loader.exec_module(hub)
class CatalogTests(unittest.TestCase):
 def test_complete_distinct_catalog(self):
  profiles=hub.validate_catalog();self.assertEqual(45,len(profiles));self.assertEqual(6,len({p['group'] for p in profiles}))
  for p in profiles:
   self.assertNotIn('PROVISIONED=1',p['flags']);self.assertNotIn('DIRECTIONS_VERIFIED=1',p['flags'])
 def fixture(self,root):
  catalog=copy.deepcopy(hub.CATALOG);catalog['profiles']=catalog['profiles'][:2]
  for p in catalog['profiles']:
   folder=root/p['id'];folder.mkdir();images=[]
   for kind,offset in hub.OFFSETS.items():
    path=folder/(kind+'.bin');path.write_bytes(b'image-'+kind.encode());images.append(dict(kind=kind,file=path.name,offset=offset,bytes=path.stat().st_size,sha256=hub.sha(path)))
   (folder/'BUILD.json').write_text(json.dumps({**p,'images':images,'provenance':{'fingerprint':'a'}}))
  return catalog
 def test_complete_package_validates(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);c=self.fixture(root);self.assertEqual(2,len(hub.verify_package(root,c)))
 def test_partial_collection_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);c=self.fixture(root);(root/c['profiles'][0]['id']/'BUILD.json').unlink()
   with self.assertRaises(RuntimeError):hub.verify_package(root,c)
 def test_corrupt_image_or_mixed_generations_rejected(self):
  for failure in ('image','generation','merged'):
   with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);c=self.fixture(root);folder=root/c['profiles'][0]['id']
    if failure=='image':(folder/'application.bin').write_bytes(b'corrupt')
    elif failure=='merged':(folder/'unsafe.merged.bin').write_bytes(b'unsafe')
    else:
     p=folder/'BUILD.json';data=json.loads(p.read_text());data['provenance']['fingerprint']='b';p.write_text(json.dumps(data))
    with self.assertRaises(AssertionError):hub.verify_package(root,c)
 def test_catalog_rejects_private_key_flags_or_path_escape(self):
  for key,value in [('flags','-DPRIVATE_KEY=secret'),('path','../../secret')]:
   c=copy.deepcopy(hub.CATALOG);c['profiles'][0][key]=value
   with self.assertRaises(AssertionError):hub.validate_catalog(c)
if __name__=='__main__':unittest.main()
