import unittest
from anticonflict import PURCHASES, Engine, run_all


class TestEngine(unittest.TestCase):
    def setUp(self):
        self.eng, self.sigs, self.elapsed, self.per_pp = run_all()
        self.gt = {p["id"]: set(p["gt"]) for p in PURCHASES if p["gt"]}

    def test_01_coverage_100(self):
        self.assertEqual(len(self.sigs), len(PURCHASES))
        self.assertEqual(len(PURCHASES), 17)

    def test_02_injections_found(self):
        for pid, rules in self.gt.items():
            got = set(s["rule"] for s in self.sigs[pid])
            self.assertEqual(got, rules,
                             "закупка %s: %s != %s" % (pid, got, rules))
        self.assertEqual(len(self.gt), 8)

    def test_03_precision_clean(self):
        clean = [p["id"] for p in PURCHASES if not p["gt"]]
        self.assertEqual(len(clean), 9)
        for pid in clean:
            self.assertEqual(self.sigs[pid], [], "ложное срабатывание: " + pid)

    def test_04_journal_chain(self):
        self.assertEqual(len(self.eng.journal), 18)
        self.assertTrue(self.eng.verify_chain())

    def test_05_determinism(self):
        e2, s2, _, _ = run_all()
        self.assertEqual(
            [(s["rule"], s["purchase"], s["fact"])
             for sigs in self.sigs.values() for s in sigs],
            [(s["rule"], s["purchase"], s["fact"])
             for sigs in s2.values() for s in sigs])

    def test_06_tamper_detected(self):
        tampered = [dict(r) for r in self.eng.journal]
        tampered[2]["signals"] = 99
        body = None
        saved = self.eng.journal
        self.eng.journal = tampered
        try:
            self.assertFalse(self.eng.verify_chain())
        finally:
            self.eng.journal = saved

    def test_07_escalation(self):
        self.assertEqual(len(self.eng.escalations), 1)
        e = self.eng.escalations[0]
        self.assertEqual(e["purchase"], "З-06")
        self.assertIn("РНП-трекер", " ".join(e["docs"]))

    def test_08_explainability(self):
        for sigs in self.sigs.values():
            for s in sigs:
                for key in ("rule", "norm", "fact", "source", "action"):
                    self.assertTrue(s.get(key), "сигнал без %s" % key)
                    self.assertNotIn("[", s["norm"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
