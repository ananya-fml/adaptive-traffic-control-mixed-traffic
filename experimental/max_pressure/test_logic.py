"""Pure-Python tests; no licensed VISSIM required."""
import json
import unittest
from pathlib import Path
from experiment import proportional_greens, pressure

C = json.loads((Path(__file__).parent / 'config.json').read_text())

class TestLogic(unittest.TestCase):
    def test_queue_green_budget(self):
        for q in ({"NS": 2, "EW": 4}, {"NS": 0, "EW": 0}, {"NS": 99, "EW": 1}):
            g = proportional_greens(q, C)
            self.assertEqual(sum(g.values()), 145)
            self.assertTrue(all(10 <= x <= 80 and isinstance(x,int) for x in g.values()))
    def test_pressure_downstream_penalty(self):
        empty = {"up": {101: 10}, "down": {}}
        full = {"up": {101: 10}, "down": {202: 8}}
        self.assertLess(pressure(full, C)["NS"], pressure(empty, C)["NS"])

if __name__ == '__main__':
    unittest.main()
