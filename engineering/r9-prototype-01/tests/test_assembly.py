"""Integration acceptance checks for the unapproved assembly checkpoint."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AssemblyOutputTests(unittest.TestCase):
    def test_nominal_lid_guard_path_and_explicit_holds(self):
        report = json.loads((ROOT / 'out/assembly/assembly-checks.json').read_text())
        self.assertTrue(report['staticInterference']['passes'])
        self.assertTrue(report['liftPath']['passes'])
        self.assertEqual(report['clearancesMm']['locatorToGuardNominalX'], 0.7)
        self.assertEqual(len(report['slotsVsRealGuards']['bearingCoverageFailures']), 26)
        self.assertFalse(report['productionApproved'])
        self.assertFalse(report['straps']['plateOnlyContactExcluded'])
        self.assertTrue(report['not_validated'])

    def test_direct_exports_in_shared_ledger(self):
        log = json.loads((ROOT / 'out/build-log.json').read_text())
        paths = {entry['path'] for entry in log['outputs']}
        if 'guards' in log['modules']:
            self.assertTrue(any('/guards/t1p2/' in path and path.endswith('.step') for path in paths))
        self.assertTrue(any('/lid/' in path and path.endswith('.step') for path in paths))
        self.assertIn('out/assembly/assembly-checks.json', paths)
        self.assertIn('out/pa12/lid/manifest.json', paths)
        self.assertEqual(len(paths), len(log['outputs']))


if __name__ == '__main__':
    unittest.main()
