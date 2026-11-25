"""Suite de tests automatisés pour Territorial Pulse (pipeline, modèles, API, PDF)."""

from __future__ import annotations

import unittest

from app.server import (
    SimulationRequest,
    bootstrap,
    custom_alerts,
    download_dataset,
    export_fiche_pdf,
    health,
    index,
    province_detail,
    simulate,
)
from src.config import PROCESSED_DIR
from src.model import TerritorialPulseModel


class TestTerritorialPulse(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.model = TerritorialPulseModel()
        cls.df = cls.model.df
        cls.meta = cls.model.metadata

    def test_panel_integrity(self) -> None:
        self.assertEqual(len(self.df), 656)
        self.assertEqual(self.df["province_id"].nunique(), 8)
        self.assertEqual(self.df["date"].nunique(), 82)
        self.assertEqual(int(self.df.isna().sum().sum()), 0)
        self.assertTrue((PROCESSED_DIR / "dataset_panel.parquet").exists())
        self.assertTrue((PROCESSED_DIR / "territorial_pulse.duckdb").exists())

    def test_tpi_and_sensitivity(self) -> None:
        self.assertTrue(self.df["tpi_score"].between(0.0, 100.0).all())
        meth = self.meta["tpi_methodology"]
        self.assertGreater(meth["expert_vs_pca_corr"], 0.90)
        self.assertGreaterEqual(meth["sensitivity"]["top3_stability_pct"], 90.0)

    def test_typology_clusters(self) -> None:
        labels = set(self.df["cluster_label"].unique())
        self.assertEqual(labels, {"Moteur", "En transition", "Fragile"})

    def test_nowcasting_beats_naive(self) -> None:
        metrics = self.meta["nowcasting"]["hcp_nowcast_metrics"]
        self.assertTrue(metrics["beats_naive"])
        self.assertLess(metrics["rmse_model"], metrics["rmse_naive"])
        self.assertEqual(len(self.meta["nowcasting"]["province_nowcasts"]), 8)

    def test_alerts_and_covid_detection(self) -> None:
        alerts = self.meta["alerts"]
        self.assertTrue(alerts["covid_2020_detected"])
        self.assertGreater(len(alerts["live_alerts"]), 0)

    def test_what_if_simulator(self) -> None:
        sim = self.model.simulate_what_if("TTA-07", {"tourism_nights_sa": 25.0, "business_creations_sa": 20.0})
        self.assertGreater(sim["delta_tpi"], 0.0)
        self.assertGreaterEqual(sim["simulated_tpi"], sim["base_tpi"])

    def test_fastapi_endpoints_and_pdf_export(self) -> None:
        self.assertEqual(index().status_code, 200)
        self.assertEqual(health()["status"], "ok")
        bs = bootstrap()
        self.assertEqual(len(bs["dates"]), 82)
        prof = province_detail("TTA-07")
        self.assertEqual(prof["province_name"], "Chefchaouen")
        sim = simulate(SimulationRequest(province_id="TTA-07", shocks_pct={"nightlights_sa": 15.0}))
        self.assertGreater(sim["delta_tpi"], 0.0)
        self.assertGreater(len(custom_alerts()["live_alerts"]), 0)
        pdf_resp = export_fiche_pdf("TTA-07")
        self.assertEqual(pdf_resp.status_code, 200)
        self.assertEqual(pdf_resp.body[:4], b"%PDF")
        dl = download_dataset("parquet")
        self.assertEqual(dl.filename, "dataset_panel.parquet")


if __name__ == "__main__":
    unittest.main(verbosity=2)
