"""Integration acceptance checks for the unapproved assembly checkpoint."""
import json
import unittest
from pathlib import Path

from r9.checks import _interval_box_distance, _interval_box_overlap_volume

ROOT = Path(__file__).resolve().parents[1]


class AssemblyOutputTests(unittest.TestCase):
    def test_conservative_envelope_math_detects_overlap_and_clearance(self):
        a = ((0, 2), (0, 2), (0, 2))
        overlap = ((1, 3), (1, 3), (1, 3))
        separated = ((5, 6), (0, 2), (0, 2))
        self.assertEqual(_interval_box_overlap_volume(a, overlap), 1)
        self.assertEqual(_interval_box_distance(a, overlap), 0)
        self.assertEqual(_interval_box_overlap_volume(a, separated), 0)
        self.assertEqual(_interval_box_distance(a, separated), 3)

    def test_nominal_lid_guard_path_and_explicit_holds(self):
        report = json.loads((ROOT / 'out/assembly/assembly-checks.json').read_text())
        self.assertTrue(report['staticInterference']['testedSolidPairsPass'])
        self.assertFalse(report['staticInterference']['complete'])
        self.assertFalse(report['staticInterference']['passes'])
        self.assertTrue(report['liftPath']['testedSolidPathPass'])
        self.assertTrue(report['liftPath']['envelopeScreenPass'])
        self.assertFalse(report['liftPath']['passes'])
        self.assertEqual(report['clearancesMm']['locatorToGuardNominalX'], 0.7)
        self.assertGreater(report['clearancesMm']['locatorToRailEnvelope'], 4)
        self.assertGreater(report['clearancesMm']['locatorToHighestBracket'], 5)
        self.assertEqual(set(report['staticInterference']['envelopeChecks']),
                         {'rail', 'bracket', 'pcb', 'otherHardware'})
        self.assertTrue(report['staticInterference']['untestedPairClasses'])
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
