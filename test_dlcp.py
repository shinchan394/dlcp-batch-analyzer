import math
import tempfile
import unittest
from pathlib import Path

from dlcp_gui import VAC_MODE_PEAK, VAC_MODE_RMS, X_FILENAME_VAC, Y_AUTO_CAP, FileRecord, build_summary, find_csv_files, fit_poly2, infer_bias_and_vac, moving_average, process_batch, process_record, vac_factor


class DLCPTests(unittest.TestCase):
    def test_quadratic_fit(self):
        x = [-0.2, 0.0, 0.1, 0.3, 0.5]
        y = [2.0 + 3.0 * a - 4.0 * a * a for a in x]
        c0, c1, c2 = fit_poly2(x, y)
        self.assertAlmostEqual(c0, 2.0, places=10)
        self.assertAlmostEqual(c1, 3.0, places=10)
        self.assertAlmostEqual(c2, -4.0, places=10)

    def test_moving_average_and_process(self):
        self.assertEqual(moving_average([1, 2, 3], 1), [1, 2, 3])
        self.assertAlmostEqual(vac_factor(VAC_MODE_PEAK), 2.0)
        self.assertAlmostEqual(vac_factor(VAC_MODE_RMS), 2.0 * math.sqrt(2.0))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bias_-1.0.csv"
            path.write_text("Vac,Cap\n0,2\n0.1,2.26\n0.2,2.44\n0.3,2.54\n", encoding="utf-8")
            result = process_record(FileRecord(str(path), bias=-1, eps_r=10, area_cm2=0.01), "Vac", "Cap", 1e-12)
            self.assertAlmostEqual(result["c0"], 2e-12, places=23)
            self.assertAlmostEqual(result["c1"], 3e-12, places=23)
            self.assertAlmostEqual(result["c2"], -4e-12, places=23)

    def test_summary_has_depth_and_density(self):
        results = []
        for bias in [-1.0, 0.0, 1.0]:
            c0 = 2e-12 + 0.2e-12 * bias
            results.append({"record": FileRecord(f"bias_{bias}.csv", bias, 10, 0.01), "x": [0, 0.1, 0.2], "y": [c0, c0 + 0.1e-12, c0 + 0.16e-12], "fit_y": [], "smooth_y": [], "derivative_fit": [], "c0": c0, "c1": 1e-12, "c2": -1e-12})
        summary = build_summary(results, 3)
        self.assertEqual(len(summary), 3)
        self.assertTrue(math.isfinite(summary[0]["depletion_width_nm"]))
        self.assertTrue(math.isfinite(summary[0]["N_CV_abs_cm-3"]))
        self.assertTrue(math.isfinite(summary[0]["N_DL_abs_cm-3"]))

    def test_peak_input_is_converted_before_fit(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bias_0.csv"
            # y = 2 + 3*dVpp - 4*dVpp^2, but x stores peak amplitude.
            path.write_text("Vac,Cap\n0,2\n0.05,2.26\n0.1,2.44\n0.15,2.54\n", encoding="utf-8")
            result = process_record(FileRecord(str(path)), "Vac", "Cap", 1e-12, vac_scale=2.0)
            self.assertAlmostEqual(result["c0"], 2e-12, places=23)
            self.assertAlmostEqual(result["c1"], 3e-12, places=23)
            self.assertAlmostEqual(result["c2"], -4e-12, places=23)
            self.assertAlmostEqual(result["x_input"][1], 0.05)
            self.assertAlmostEqual(result["x"][1], 0.1)

    def test_filename_vac_and_duplicate_capacitance_rows_are_averaged(self):
        with tempfile.TemporaryDirectory() as temp:
            records = []
            for vac_mv in [20, 40, 60, 80, 100]:
                vac_v = vac_mv / 1000.0
                c_pf = 2.0 + 3.0 * vac_v - 4.0 * vac_v * vac_v
                path = Path(temp) / f"-175mV {vac_mv}mV_000_Gp_over_omega_prepared.csv"
                csv_bias = -0.175 - vac_v
                path.write_text(f"index,bias_V,capacitance_F\n1,{csv_bias},{(c_pf-0.01)*1e-12}\n2,{csv_bias},{(c_pf+0.01)*1e-12}\n", encoding="utf-8")
                bias, inferred_vac = infer_bias_and_vac(str(path), 0.0)
                records.append(FileRecord(str(path), bias=bias, eps_r=17, area_cm2=0.09, vac_input=inferred_vac))
            result = process_batch(records, X_FILENAME_VAC, Y_AUTO_CAP, 1.0, vac_scale=1.0)
            self.assertAlmostEqual(result["record"].bias, -0.175)
            self.assertEqual(len(result["x"]), 5)
            self.assertAlmostEqual(result["c0"], 2e-12, places=23)
            self.assertAlmostEqual(result["c1"], 3e-12, places=23)
            self.assertAlmostEqual(result["c2"], -4e-12, places=23)
            summary = build_summary([result], 3)
            self.assertEqual(summary[0]["N_CV_method"], "CSV bias_V vs C")
            self.assertTrue(math.isfinite(summary[0]["depletion_width_nm"]))
            self.assertTrue(math.isfinite(summary[0]["N_CV_abs_cm-3"]))

    def test_find_csv_files_recursively(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "-175mV").mkdir()
            (root / "0V").mkdir()
            (root / "-175mV" / "-175mV 20mV.csv").write_text("Vac,Cap\n0.02,1\n", encoding="utf-8")
            (root / "0V" / "0V 20mV.csv").write_text("Vac,Cap\n0.02,1\n", encoding="utf-8")
            (root / "notes.txt").write_text("ignore", encoding="utf-8")
            found = find_csv_files(str(root))
            self.assertEqual(len(found), 2)
            self.assertTrue(all(path.lower().endswith(".csv") for path in found))


if __name__ == "__main__":
    unittest.main()
