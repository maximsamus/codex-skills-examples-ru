import unittest
from main import total

class TotalTest(unittest.TestCase):
    def test_total(self):
        self.assertEqual(total(2, 3), 5)
