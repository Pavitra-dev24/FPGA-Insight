import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import unittest
import numpy as np
class TestFPGASimulator(unittest.TestCase):

    def setUp(self):
        from core.fpga_sim import FPGASimulator
        self.fpga = FPGASimulator()

    def test_initial_registers_populated(self):
        self.assertEqual(len(self.fpga.regs), 12)

    def test_read_register(self):
        val = self.fpga.read_register("0x00")
        self.assertEqual(val, 0x01)

    def test_write_writable_register(self):
        ok, msg = self.fpga.write_register("0x04", 0xFF)
        self.assertTrue(ok)
        self.assertEqual(self.fpga.read_register("0x04"), 0xFF)

    def test_write_readonly_register_rejected(self):
        ok, msg = self.fpga.write_register("0x01", 0xFF)
        self.assertFalse(ok)

    def test_write_nonexistent_register(self):
        ok, msg = self.fpga.write_register("0xFF", 0x00)
        self.assertFalse(ok)

    def test_value_masked_to_byte(self):
        self.fpga.write_register("0x04", 0x1FF)
        self.assertEqual(self.fpga.read_register("0x04"), 0xFF)

    def test_clk_div_side_effect(self):
        self.fpga.write_register("0x02", 8)
        self.assertAlmostEqual(self.fpga.clk_freq_mhz, 50.0, places=1)

    def test_pwr_mgmt_sleep(self):
        self.fpga.write_register("0x0A", 0)
        self.assertAlmostEqual(self.fpga.power_w, 0.05, places=2)

    def test_get_signals_shape(self):
        sigs = self.fpga.get_signals(120)
        for key in ("time", "CLK", "GPIO", "ADC", "VOLTAGE"):
            self.assertIn(key, sigs)
            self.assertEqual(len(sigs[key]), 120)

    def test_get_feature_vector_length(self):
        fv = self.fpga.get_feature_vector()
        self.assertEqual(len(fv), 7)

    def test_anomaly_injection(self):
        self.fpga.inject_anomaly()
        self.assertTrue(self.fpga.anomaly_mode)

    def test_anomaly_clear(self):
        self.fpga.inject_anomaly()
        self.fpga.clear_anomaly()
        self.assertFalse(self.fpga.anomaly_mode)

    def test_reset_registers(self):
        self.fpga.write_register("0x04", 0x00)
        self.fpga.reset_registers()
        self.assertEqual(self.fpga.read_register("0x04"), 0xAA)

    def test_tick_sensors_changes_values(self):
        for _ in range(20):
            self.fpga.tick_sensors()
        temp = self.fpga.regs["0x07"]["value"]
        self.assertGreater(temp, 0)
        self.assertLess(temp, 0xFF)
class TestAnomalyDetector(unittest.TestCase):

    def setUp(self):
        from core.ai_engine import AnomalyDetector
        self.det = AnomalyDetector()

    def _make_normal_features(self):
        return [0.05, 0.80, 0.06, 0.04, 3.30, 0.02, 26.0]

    def _train(self):
        from core.ai_engine import TRAIN_SAMPLES
        for _ in range(TRAIN_SAMPLES):
            fv = self._make_normal_features()
            fv = [x + np.random.normal(0, 0.01) for x in fv]
            self.det.add_training_sample(fv)

    def test_not_trained_initially(self):
        self.assertFalse(self.det.trained)

    def test_trains_after_enough_samples(self):
        self._train()
        self.assertTrue(self.det.trained)

    def test_score_returns_tuple_of_3(self):
        self._train()
        result = self.det.score(self._make_normal_features())
        self.assertEqual(len(result), 3)

    def test_normal_data_scores_positive_or_near_zero(self):
        self.det = self._fresh_trained()
        _, score, severity = self.det.score(self._make_normal_features())
        self.assertGreater(score, -0.45)

    def test_extreme_anomaly_detected(self):
        self.det = self._fresh_trained()
        anomaly_fv = [5.0, 5.0, 5.0, 5.0, 9.0, 5.0, 200.0]
        is_anom, score, severity = self.det.score(anomaly_fv)
        self.assertTrue(is_anom)

    def test_training_progress_0_to_1(self):
        p0 = self.det.training_progress()
        self.assertEqual(p0, 0.0)
        self._train()
        p1 = self.det.training_progress()
        self.assertGreaterEqual(p1, 1.0)

    def test_score_history_accumulates(self):
        self._train()
        for _ in range(5):
            self.det.score(self._make_normal_features())
        scores, labels = self.det.get_score_history()
        self.assertEqual(len(scores), 5)

    def _fresh_trained(self):
        from core.ai_engine import AnomalyDetector, TRAIN_SAMPLES
        det = AnomalyDetector()
        for _ in range(TRAIN_SAMPLES):
            fv = [x + np.random.normal(0, 0.01) for x in self._make_normal_features()]
            det.add_training_sample(fv)
        return det
class TestNLPParser(unittest.TestCase):

    def setUp(self):
        from core.fpga_sim  import FPGASimulator
        from core.nlp_parser import NLPParser
        self.fpga   = FPGASimulator()
        self.parser = NLPParser(self.fpga)

    def test_set_by_name_decimal(self):
        r = self.parser.parse("set GPIO_OUT to 255")
        self.assertEqual(r["cmd"], "set")
        self.assertTrue(r["success"])
        self.assertEqual(self.fpga.read_register("0x04"), 255)

    def test_set_by_name_hex(self):
        r = self.parser.parse("set GPIO_OUT to 0xFF")
        self.assertTrue(r["success"])
        self.assertEqual(self.fpga.read_register("0x04"), 0xFF)

    def test_set_by_addr(self):
        r = self.parser.parse("set 0x04 to 0x00")
        self.assertTrue(r["success"])
        self.assertEqual(self.fpga.read_register("0x04"), 0x00)

    def test_set_readonly_rejected(self):
        r = self.parser.parse("set STATUS_REG to 0xFF")
        self.assertFalse(r["success"])

    def test_read_by_name(self):
        r = self.parser.parse("read CTRL_REG")
        self.assertEqual(r["cmd"], "read")
        self.assertTrue(r["success"])
        self.assertEqual(r["value"], 0x01)

    def test_read_by_addr(self):
        r = self.parser.parse("read 0x00")
        self.assertTrue(r["success"])

    def test_reset_all(self):
        self.fpga.write_register("0x04", 0x00)
        r = self.parser.parse("reset all")
        self.assertTrue(r["success"])
        self.assertEqual(self.fpga.read_register("0x04"), 0xAA)

    def test_inject_anomaly(self):
        r = self.parser.parse("inject anomaly")
        self.assertTrue(r["success"])
        self.assertTrue(self.fpga.anomaly_mode)

    def test_clear_anomaly(self):
        self.fpga.inject_anomaly()
        r = self.parser.parse("clear anomaly")
        self.assertTrue(r["success"])
        self.assertFalse(self.fpga.anomaly_mode)

    def test_show_status(self):
        r = self.parser.parse("show status")
        self.assertEqual(r["cmd"], "status")
        self.assertTrue(r["success"])
        self.assertIn("Clock", r["message"])

    def test_run_diagnostic(self):
        r = self.parser.parse("run diagnostic")
        self.assertEqual(r["cmd"], "diagnostic")
        self.assertTrue(r["success"])

    def test_export_cmd(self):
        r = self.parser.parse("export config")
        self.assertEqual(r["cmd"], "export")
        self.assertTrue(r["success"])

    def test_help_cmd(self):
        r = self.parser.parse("help")
        self.assertEqual(r["cmd"], "help")
        self.assertTrue(r["success"])

    def test_unknown_command(self):
        r = self.parser.parse("do something crazy")
        self.assertFalse(r["success"])
        self.assertEqual(r["cmd"], "unknown")

    def test_invalid_register_name(self):
        r = self.parser.parse("set FAKENAME to 0x01")
        self.assertFalse(r["success"])

    def test_invalid_value(self):
        r = self.parser.parse("set GPIO_OUT to xyz")
        self.assertFalse(r["success"])

    def test_history_recorded(self):
        self.parser.parse("help")
        self.parser.parse("show status")
        self.assertEqual(len(self.parser.history), 2)

    def test_case_insensitive(self):
        r = self.parser.parse("SET GPIO_OUT TO 0xAB")
        self.assertTrue(r["success"])
if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestFPGASimulator))
    suite.addTests(loader.loadTestsFromTestCase(TestAnomalyDetector))
    suite.addTests(loader.loadTestsFromTestCase(TestNLPParser))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
