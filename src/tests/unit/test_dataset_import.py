"""CAN-016b: tests for dataset_import.parse_csv_bytes + DemoMode.import_dataset.

Covers the CSV parser exhaustively (header detection, format errors, size
caps, label coercion) and the DemoMode integration smoke-tests via a fake
network fixture so we don't need the full demo backend stack.
"""

import numpy as np
import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def parse_csv_bytes():
    from dataset_import import parse_csv_bytes as _parse

    return _parse


@pytest.fixture
def DatasetImportError():
    from dataset_import import DatasetImportError as _err

    return _err


class TestParseCsvBytesHappyPath:
    """Happy-path coverage of the CSV parser."""

    def test_simple_two_features_two_classes(self, parse_csv_bytes):
        raw = b"0.1,0.2,0\n0.3,0.4,1\n0.5,0.6,0\n"
        inputs, targets = parse_csv_bytes(raw)
        assert inputs.shape == (3, 2)
        assert targets.shape == (3,)
        assert inputs.dtype == np.float32
        assert targets.dtype == np.int64
        np.testing.assert_array_almost_equal(inputs, [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]])
        np.testing.assert_array_equal(targets, [0, 1, 0])

    def test_header_row_auto_detected(self, parse_csv_bytes):
        raw = b"x1,x2,label\n0.1,0.2,0\n0.3,0.4,1\n"
        inputs, targets = parse_csv_bytes(raw)
        assert inputs.shape == (2, 2)
        np.testing.assert_array_equal(targets, [0, 1])

    def test_high_dimensional_features(self, parse_csv_bytes):
        # 5 features + label
        raw = b"0,0,0,0,0,0\n1,1,1,1,1,1\n"
        inputs, targets = parse_csv_bytes(raw)
        assert inputs.shape == (2, 5)
        assert targets.shape == (2,)

    def test_blank_lines_skipped(self, parse_csv_bytes):
        raw = b"0.1,0.2,0\n\n0.3,0.4,1\n   \n"
        inputs, targets = parse_csv_bytes(raw)
        assert inputs.shape == (2, 2)

    def test_whitespace_around_values(self, parse_csv_bytes):
        raw = b" 0.1 , 0.2 , 0 \n 0.3, 0.4 ,1\n"
        inputs, targets = parse_csv_bytes(raw)
        np.testing.assert_array_almost_equal(inputs, [[0.1, 0.2], [0.3, 0.4]])
        np.testing.assert_array_equal(targets, [0, 1])


class TestParseCsvBytesErrors:
    """Error-path coverage. Each surfaces a user-readable DatasetImportError."""

    def test_empty_payload_rejected(self, parse_csv_bytes, DatasetImportError):
        with pytest.raises(DatasetImportError, match="empty"):
            parse_csv_bytes(b"")

    def test_non_bytes_rejected(self, parse_csv_bytes, DatasetImportError):
        with pytest.raises(DatasetImportError, match="bytes"):
            parse_csv_bytes("not-bytes")  # type: ignore[arg-type]

    def test_oversized_rejected(self, parse_csv_bytes, DatasetImportError):
        # Force the cap low so we don't have to allocate 10 MB.
        with pytest.raises(DatasetImportError, match="too large"):
            parse_csv_bytes(b"a" * 1000, max_bytes=100)

    def test_non_utf8_rejected(self, parse_csv_bytes, DatasetImportError):
        # Lone 0x80 byte is invalid UTF-8.
        with pytest.raises(DatasetImportError, match="UTF-8"):
            parse_csv_bytes(b"\x80\x81\x82")

    def test_only_header_rejected(self, parse_csv_bytes, DatasetImportError):
        with pytest.raises(DatasetImportError, match="no data rows"):
            parse_csv_bytes(b"x1,x2,label\n")

    def test_single_column_rejected(self, parse_csv_bytes, DatasetImportError):
        with pytest.raises(DatasetImportError, match="at least 2 columns"):
            parse_csv_bytes(b"0.1\n0.2\n")

    def test_inconsistent_columns_rejected(self, parse_csv_bytes, DatasetImportError):
        raw = b"0.1,0.2,0\n0.3,0.4,0.5,1\n"
        with pytest.raises(DatasetImportError, match="Row 2"):
            parse_csv_bytes(raw)

    def test_non_numeric_feature_rejected(self, parse_csv_bytes, DatasetImportError):
        raw = b"0.1,abc,0\n0.3,0.4,1\n"
        with pytest.raises(DatasetImportError, match="Row 1"):
            parse_csv_bytes(raw)

    def test_non_numeric_label_rejected(self, parse_csv_bytes, DatasetImportError):
        raw = b"0.1,0.2,cat\n0.3,0.4,dog\n"
        with pytest.raises(DatasetImportError, match="Row 1"):
            parse_csv_bytes(raw)

    def test_float_label_rejected(self, parse_csv_bytes, DatasetImportError):
        raw = b"0.1,0.2,0.5\n0.3,0.4,1.5\n"
        with pytest.raises(DatasetImportError, match="not an integer"):
            parse_csv_bytes(raw)

    def test_negative_label_rejected(self, parse_csv_bytes, DatasetImportError):
        raw = b"0.1,0.2,-1\n0.3,0.4,0\n"
        with pytest.raises(DatasetImportError, match="non-negative"):
            parse_csv_bytes(raw)


class TestParseCsvBytesLimits:
    def test_too_many_rows(self, parse_csv_bytes, DatasetImportError):
        # MAX_ROWS=50_000; build 50_001 lines of "0,0,0".
        from dataset_import import MAX_ROWS

        body = "0,0,0\n" * (MAX_ROWS + 1)
        with pytest.raises(DatasetImportError, match="Too many rows"):
            parse_csv_bytes(body.encode("utf-8"))

    def test_too_many_features(self, parse_csv_bytes, DatasetImportError):
        from dataset_import import MAX_FEATURES

        # MAX_FEATURES + 1 feature columns + 1 label column = MAX_FEATURES + 2 cols
        cols = ["0.0"] * (MAX_FEATURES + 1) + ["0"]
        row = ",".join(cols) + "\n"
        body = row * 3
        with pytest.raises(DatasetImportError, match="feature columns"):
            parse_csv_bytes(body.encode("utf-8"))


class TestDemoModeImportDataset:
    """DemoMode.import_dataset integration. Uses a minimal fake network so we
    don't need the full demo backend stack (no torch.no_grad context managers,
    no juniper-data calls)."""

    def _make_demo_with_fake_network(self):
        """Construct a DemoMode and inject a stub network that has the fields
        ``import_dataset`` writes to (train_x / train_y)."""
        from demo_mode import DemoMode

        # Build via __new__ to skip the real __init__ which spins up worker threads.
        demo = DemoMode.__new__(DemoMode)
        import threading

        demo._lock = threading.RLock()
        demo._pause = threading.Event()
        demo.running = False
        demo.is_running = False
        demo.dataset = {}
        demo.metrics_history = []
        demo.current_epoch = 99
        demo.current_loss = 0.5
        demo.current_accuracy = 0.7

        class _FakeNetwork:
            train_x = None
            train_y = None
            hidden_units = []

        demo.network = _FakeNetwork()

        class _StubLogger:
            def info(self, *a, **k):
                pass

            def warning(self, *a, **k):
                pass

            def debug(self, *a, **k):
                pass

        demo.logger = _StubLogger()
        return demo

    def test_import_replaces_dataset_atomically(self):
        torch = pytest.importorskip("torch")
        demo = self._make_demo_with_fake_network()
        inputs = np.array([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]], dtype=np.float32)
        targets = np.array([0, 1, 0], dtype=np.int64)

        result = demo.import_dataset(inputs, targets, source_label="upload:test.csv")

        assert result["n_samples"] == 3
        assert result["n_features"] == 2
        assert result["n_classes"] == 2
        assert result["source"] == "upload:test.csv"
        # train_x / train_y must be torch tensors with the imported values.
        assert torch.is_tensor(demo.network.train_x)
        assert demo.network.train_x.shape == (3, 2)
        assert demo.network.train_y.shape == (3,)
        # Counters reset.
        assert demo.current_epoch == 0
        assert demo.current_loss == 1.0
        assert demo.current_accuracy == 0.5
        assert demo.metrics_history == []

    def test_import_rejects_shape_mismatch(self):
        pytest.importorskip("torch")
        demo = self._make_demo_with_fake_network()
        with pytest.raises(ValueError, match="length matching"):
            demo.import_dataset(np.zeros((3, 2)), np.zeros(2))

    def test_import_rejects_one_dim_inputs(self):
        pytest.importorskip("torch")
        demo = self._make_demo_with_fake_network()
        with pytest.raises(ValueError, match="2-D"):
            demo.import_dataset(np.zeros(5), np.zeros(5))

    def test_import_rejects_empty(self):
        pytest.importorskip("torch")
        demo = self._make_demo_with_fake_network()
        with pytest.raises(ValueError, match="at least 1 row"):
            demo.import_dataset(np.zeros((0, 2)), np.zeros(0))


class TestDatasetImportSourceWiring:
    """Source-level invariants on the canopy frontend wiring (matches the
    pattern used elsewhere in test_phase_b_bridge.py for JS / dashboard
    invariants)."""

    @pytest.fixture
    def dataset_plotter_source(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "frontend" / "components" / "dataset_plotter.py"
        return path.read_text(encoding="utf-8")

    @pytest.fixture
    def main_source(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "main.py"
        return path.read_text(encoding="utf-8")

    @pytest.fixture
    def dashboard_manager_source(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "frontend" / "dashboard_manager.py"
        return path.read_text(encoding="utf-8")

    def test_modal_has_three_tabs(self, dataset_plotter_source):
        assert "tab-generate" in dataset_plotter_source
        assert "tab-upload" in dataset_plotter_source
        assert "tab-url" in dataset_plotter_source

    def test_upload_tab_uses_dcc_upload(self, dataset_plotter_source):
        assert "dcc.Upload(" in dataset_plotter_source
        assert "import-file-upload" in dataset_plotter_source

    def test_url_tab_has_input(self, dataset_plotter_source):
        assert "import-url-input" in dataset_plotter_source
        assert "import-url-confirm" in dataset_plotter_source

    def test_main_has_import_file_endpoint(self, main_source):
        assert '@app.post("/api/dataset/import-file")' in main_source
        assert "UploadFile = File(...)" in main_source

    def test_main_has_import_url_endpoint(self, main_source):
        assert '@app.post("/api/dataset/import-url")' in main_source

    def test_main_endpoints_demo_only(self, main_source):
        """Both endpoints must guard on demo-mode (cascor backend doesn't yet
        accept inline datasets — surfaces a clear 400 instead of a confusing
        500)."""
        # Two demo-mode guards should be present (one per endpoint).
        assert main_source.count('backend.backend_type != "demo"') >= 2

    def test_dashboard_manager_wires_import_callbacks(self, dashboard_manager_source):
        assert "_import_dataset_file_handler" in dashboard_manager_source
        assert "_import_dataset_url_handler" in dashboard_manager_source
        assert "import-file-confirm" in dashboard_manager_source
        assert "import-url-confirm" in dashboard_manager_source
