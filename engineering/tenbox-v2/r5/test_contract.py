"""Small failure fixtures for ZIP atomic delivery and literal Studio dispatch."""
from pathlib import Path
import hashlib, importlib.util, tempfile, unittest, zipfile
import build
ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('studio', ROOT/'source/h2d-r5/verify_studio_import_contract.py')
studio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(studio)

class DeliveryContract(unittest.TestCase):
    def test_literal_relationship_is_required(self):
        ns = studio.RELS
        kind = 'http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel'
        good = f'<Relationships xmlns="{ns}"><Relationship Id="r" Type="{kind}" Target="/3D/3dmodel.model"/></Relationships>'.encode()
        bad = f'<ns0:Relationships xmlns:ns0="{ns}"><ns0:Relationship Id="r" Type="{kind}" Target="/3D/3dmodel.model"/></ns0:Relationships>'.encode()
        self.assertEqual(studio.root_model_targets(good), ['/3D/3dmodel.model'])
        self.assertEqual(studio.root_model_targets(bad), [])

    def test_complete_manifest_crc_and_truncated_zip(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)/'out.zip'
            build.atomic_zip(target, {'current-floor.stl': b'floor', 'projects/a.3mf': b'project'})
            self.assertEqual(set(build.verify_zip(target)), {'current-floor.stl', 'projects/a.3mf', 'MANIFEST.sha256'})
            original = target.read_bytes()
            truncated = Path(temporary)/'truncated.zip'
            truncated.write_bytes(original[:-22])
            with self.assertRaises(zipfile.BadZipFile):
                build.verify_zip(truncated)
            build.atomic_zip(target, {'current-floor.stl': b'floor', 'projects/a.3mf': b'project'})
            self.assertEqual(target.read_bytes(), original)

    def test_wrong_manifest_hash_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)/'tampered.zip'
            with zipfile.ZipFile(target, 'w') as archive:
                archive.writestr('floor.stl', b'bad')
                archive.writestr('MANIFEST.sha256', '0'*64+'  floor.stl\n')
            with self.assertRaises(AssertionError):
                build.verify_zip(target)

    def test_duplicate_manifest_row_cannot_hide_unverified_member(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)/'hidden-member.zip'
            sha = hashlib.sha256(b'floor').hexdigest()
            with zipfile.ZipFile(target, 'w') as archive:
                archive.writestr('floor.stl', b'floor')
                archive.writestr('unverified.stl', b'unchecked')
                archive.writestr('MANIFEST.sha256', (sha+'  floor.stl\n')*2)
            with self.assertRaises(AssertionError):
                build.verify_zip(target)

    def test_duplicate_archive_member_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)/'duplicate.zip'
            with zipfile.ZipFile(target, 'w') as archive:
                archive.writestr('a', b'a')
                archive.writestr('a', b'a')
                archive.writestr('MANIFEST.sha256', '')
            with self.assertRaises(AssertionError):
                build.verify_zip(target)

if __name__ == '__main__':
    unittest.main()
