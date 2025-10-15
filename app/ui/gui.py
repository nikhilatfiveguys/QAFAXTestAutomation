"""Desktop GUI for the QAFAX automation platform."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

try:  # pragma: no cover - runtime optional dependency guard
    from PySide6.QtCore import QThread, Signal, Slot, QUrl, Qt, QTimer
    from PySide6.QtGui import (
        QAction,
        QDesktopServices,
        QGuiApplication,
        QColor,
        QLinearGradient,
        QPainter,
        QPainterPath,
    )
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QPlainTextEdit,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )
except ImportError as import_error:  # pragma: no cover - handled at launch time
    PySide6_IMPORT_ERROR = import_error
    QApplication = None  # type: ignore[assignment]
else:  # pragma: no cover - GUI logic exercised manually
    PySide6_IMPORT_ERROR = None

from ..core.execution import RunOptions, execute_run, DEFAULT_SNMP_OIDS
from ..core.config_service import ConfigService, default_config_service


if QApplication is not None:  # pragma: no cover - requires GUI loop

    class OceanWaveWidget(QWidget):
        """Animated ocean wave widget used for splash and loading screens."""

        def __init__(self, parent: Optional[QWidget] = None) -> None:
            super().__init__(parent)
            self._phase = 0.0
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._advance_phase)
            self._timer.start(30)
            self.setMinimumHeight(160)

        def _advance_phase(self) -> None:
            self._phase = (self._phase + 0.18) % (2 * math.pi)
            self.update()

        def _draw_wave(
            self,
            painter: QPainter,
            rect_width: int,
            rect_height: int,
            amplitude: float,
            baseline_ratio: float,
            phase_offset: float,
            color: QColor,
        ) -> None:
            baseline = rect_height * baseline_ratio
            path = QPainterPath()
            path.moveTo(0, rect_height)
            path.lineTo(0, baseline)
            for x in range(0, rect_width + 1, 4):
                theta = (x / max(1, rect_width)) * 2 * math.pi
                y = baseline + math.sin(theta + self._phase + phase_offset) * amplitude
                path.lineTo(x, y)
            path.lineTo(rect_width, rect_height)
            path.closeSubpath()
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawPath(path)

        def paintEvent(self, event) -> None:  # type: ignore[override]
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            rect = self.rect()

            gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            gradient.setColorAt(0.0, QColor(0, 49, 96))
            gradient.setColorAt(1.0, QColor(0, 98, 130))
            painter.fillRect(rect, gradient)

            self._draw_wave(
                painter,
                rect.width(),
                rect.height(),
                amplitude=rect.height() * 0.12,
                baseline_ratio=0.65,
                phase_offset=0.0,
                color=QColor(0, 180, 216, 200),
            )
            self._draw_wave(
                painter,
                rect.width(),
                rect.height(),
                amplitude=rect.height() * 0.18,
                baseline_ratio=0.7,
                phase_offset=math.pi / 2,
                color=QColor(0, 125, 190, 170),
            )


    class WaveSplashScreen(QWidget):
        """Splash screen with animated ocean waves for application launch."""

        minimum_display_ms = 1500

        def __init__(self) -> None:
            super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.setAttribute(Qt.WA_TranslucentBackground)
            self._wave = OceanWaveWidget(self)
            self._label = QLabel("QAFAX is launching…", self)
            self._label.setAlignment(Qt.AlignCenter)
            self._label.setStyleSheet("color: white; font-size: 18px; font-weight: 600;")

            frame = QFrame(self)
            frame.setObjectName("waveFrame")
            frame.setStyleSheet(
                "#waveFrame {"
                "    background-color: rgba(7, 25, 56, 235);"
                "    border-radius: 20px;"
                "}"
                "QLabel { color: white; }"
            )

            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(40, 40, 40, 40)
            frame_layout.setSpacing(24)
            frame_layout.addWidget(self._wave)
            frame_layout.addWidget(self._label)

            root_layout = QVBoxLayout(self)
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.addStretch(1)
            root_layout.addWidget(frame, alignment=Qt.AlignCenter)
            root_layout.addStretch(1)

            self.resize(520, 360)
            self._center_on_screen()

        def _center_on_screen(self) -> None:
            screen = QGuiApplication.primaryScreen()
            if not screen:
                return
            geometry = screen.geometry()
            self.move(
                geometry.center().x() - self.width() // 2,
                geometry.center().y() - self.height() // 2,
            )

        def set_status(self, text: str) -> None:
            self._label.setText(text)


    class LoadingOverlay(QDialog):
        """Modal loading overlay with the ocean wave animation."""

        def __init__(self, parent: QWidget) -> None:
            super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog)
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setWindowModality(Qt.ApplicationModal)
            self.setModal(True)
            self._wave = OceanWaveWidget(self)
            self._label = QLabel("Preparing…", self)
            self._label.setAlignment(Qt.AlignCenter)
            self._label.setStyleSheet("color: white; font-size: 16px; font-weight: 500;")

            container = QFrame(self)
            container.setObjectName("overlayFrame")
            container.setStyleSheet(
                "#overlayFrame {"
                "    background-color: rgba(7, 25, 56, 235);"
                "    border-radius: 20px;"
                "}"
                "QLabel { color: white; }"
            )
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(32, 32, 32, 32)
            container_layout.setSpacing(16)
            container_layout.addWidget(self._wave)
            container_layout.addWidget(self._label)

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addStretch(1)
            layout.addWidget(container, alignment=Qt.AlignCenter)
            layout.addStretch(1)

        def sync_geometry(self) -> None:
            parent = self.parentWidget()
            if parent is None:
                return
            self.setGeometry(parent.rect())

        def show_message(self, message: str) -> None:
            self._label.setText(message)
            self.sync_geometry()
            if not self.isVisible():
                self.show()

        def hide_overlay(self) -> None:
            if self.isVisible():
                self.hide()

        def showEvent(self, event) -> None:  # type: ignore[override]
            self.sync_geometry()
            super().showEvent(event)


    class RunWorker(QThread):
        """Background worker that executes a fax QA run."""

        progress = Signal(str)
        completed = Signal(object)
        failed = Signal(Exception)

        def __init__(self, options: RunOptions, config_service: ConfigService) -> None:
            super().__init__()
            self._options = options
            self._config_service = config_service

        def run(self) -> None:  # type: ignore[override]
            try:
                self.progress.emit("Starting run...")
                result = execute_run(self._options, config_service=self._config_service)
            except Exception as exc:  # pragma: no cover - surfaced to UI
                self.failed.emit(exc)
            else:
                self.completed.emit(result)


    class MainWindow(QMainWindow):
        """Primary window for the desktop workflow."""

        def __init__(self, config_service: Optional[ConfigService] = None) -> None:
            super().__init__()
            self.setWindowTitle("QAFAX Desktop")
            self.resize(960, 720)

            self._config_service = config_service or default_config_service()
            self._worker: Optional[RunWorker] = None
            self._last_result_dir: Optional[Path] = None

            self._build_ui()
            self._load_defaults()
            self._loading_overlay = LoadingOverlay(self)

    # ------------------------------------------------------------------ UI setup
    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self._status_label = QLabel("Configure a run and press 'Run QA'.")
        layout.addWidget(self._status_label)

        form = QFormLayout()

        self.reference_edit, ref_button = self._file_picker("Select reference document")
        form.addRow("Reference document", self._combine(ref_button, self.reference_edit))

        self.candidate_edit, cand_button = self._file_picker("Select candidate document")
        form.addRow("Candidate document", self._combine(cand_button, self.candidate_edit))

        self.output_edit, output_button = self._directory_picker("Select artifacts directory")
        form.addRow("Artifacts directory", self._combine(output_button, self.output_edit))

        self.run_id_edit = QLineEdit("gui-run")
        form.addRow("Run ID", self.run_id_edit)

        self.iterations_spin = QSpinBox()
        self.iterations_spin.setRange(1, 1000)
        self.iterations_spin.setValue(1)
        form.addRow("Iterations", self.iterations_spin)

        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 2**31 - 1)
        self.seed_spin.setValue(1234)
        form.addRow("Seed", self.seed_spin)

        self.profile_combo = QComboBox()
        form.addRow("Profile", self.profile_combo)

        self.policy_combo = QComboBox()
        form.addRow("Policy", self.policy_combo)

        self.path_combo = QComboBox()
        self.path_combo.addItems(["digital", "print-scan"])
        form.addRow("Path", self.path_combo)

        self.transport_combo = QComboBox()
        self.transport_combo.addItems(["sim", "t38", "modem"])
        form.addRow("Transport", self.transport_combo)

        self.did_edit = QLineEdit()
        form.addRow("DID", self.did_edit)

        self.pcfax_edit = QLineEdit()
        form.addRow("HP PC-Fax queue", self.pcfax_edit)

        self.ingest_dir_edit, ingest_dir_button = self._directory_picker("Select ingest directory")
        form.addRow("Ingest directory", self._combine(ingest_dir_button, self.ingest_dir_edit))

        self.ingest_pattern_edit = QLineEdit("*")
        form.addRow("Ingest pattern", self.ingest_pattern_edit)

        self.ingest_timeout_spin = QDoubleSpinBox()
        self.ingest_timeout_spin.setRange(0.0, 3600.0)
        self.ingest_timeout_spin.setDecimals(1)
        self.ingest_timeout_spin.setValue(0.0)
        form.addRow("Ingest timeout (s)", self.ingest_timeout_spin)

        self.ingest_interval_spin = QDoubleSpinBox()
        self.ingest_interval_spin.setRange(0.1, 60.0)
        self.ingest_interval_spin.setDecimals(1)
        self.ingest_interval_spin.setValue(1.0)
        form.addRow("Ingest interval (s)", self.ingest_interval_spin)

        self.require_ocr_check = QCheckBox("Require OCR")
        form.addRow(self.require_ocr_check)

        self.require_barcode_check = QCheckBox("Require barcode")
        form.addRow(self.require_barcode_check)

        layout.addLayout(form)

        # Connector group boxes -------------------------------------------------
        snmp_group = QGroupBox("SNMP Snapshot")
        snmp_layout = QFormLayout()
        self.snmp_target_edit = QLineEdit()
        self.snmp_community_edit = QLineEdit("public")
        self.snmp_oids_edit = QLineEdit(",".join(DEFAULT_SNMP_OIDS))
        snmp_layout.addRow("Target", self.snmp_target_edit)
        snmp_layout.addRow("Community", self.snmp_community_edit)
        snmp_layout.addRow("OIDs", self.snmp_oids_edit)
        snmp_group.setLayout(snmp_layout)
        layout.addWidget(snmp_group)

        foip_group = QGroupBox("FoIP Validation")
        foip_layout = QFormLayout()
        self.foip_config_edit, foip_button = self._file_picker("Select FoIP config")
        foip_layout.addRow("FoIP config", self._combine(foip_button, self.foip_config_edit))
        foip_group.setLayout(foip_layout)
        layout.addWidget(foip_group)

        transport_group = QGroupBox("Built-in transport configuration")
        transport_layout = QFormLayout()
        self.t38_config_edit, t38_button = self._file_picker("Select T.38 config")
        self.modem_config_edit, modem_button = self._file_picker("Select modem config")
        transport_layout.addRow("T.38 config", self._combine(t38_button, self.t38_config_edit))
        transport_layout.addRow("Modem config", self._combine(modem_button, self.modem_config_edit))
        transport_group.setLayout(transport_layout)
        layout.addWidget(transport_group)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, stretch=1)

        button_row = QHBoxLayout()
        self.run_button = QPushButton("Run QA")
        self.run_button.clicked.connect(self._start_run)
        button_row.addWidget(self.run_button)

        self.open_artifacts_button = QPushButton("Open artifacts folder")
        self.open_artifacts_button.setEnabled(False)
        self.open_artifacts_button.clicked.connect(self._open_artifacts)
        button_row.addWidget(self.open_artifacts_button)

        layout.addLayout(button_row)

        # menu
        help_action = QAction("About", self)
        help_action.triggered.connect(self._show_about)
        self.menuBar().addAction(help_action)

    def _combine(self, button: QPushButton, line_edit: QLineEdit) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(line_edit)
        layout.addWidget(button)
        widget.setLayout(layout)
        return widget

    def _file_picker(self, title: str) -> tuple[QLineEdit, QPushButton]:
        edit = QLineEdit()
        button = QPushButton("Browse…")

        def choose_file() -> None:
            path, _ = QFileDialog.getOpenFileName(self, title)
            if path:
                edit.setText(path)

        button.clicked.connect(choose_file)
        return edit, button

    def _directory_picker(self, title: str) -> tuple[QLineEdit, QPushButton]:
        edit = QLineEdit()
        button = QPushButton("Browse…")

        def choose_dir() -> None:
            path = QFileDialog.getExistingDirectory(self, title)
            if path:
                edit.setText(path)

        button.clicked.connect(choose_dir)
        return edit, button

    def _load_defaults(self) -> None:
        profiles = sorted(p.stem for p in (self._config_service.base_path / "profiles").glob("*.json"))
        policies = sorted(
            path.name.split(".")[1]
            for path in self._config_service.base_path.glob("verify_policy.*.json")
        )
        if profiles:
            self.profile_combo.addItems(profiles)
        else:
            self.profile_combo.addItem("Brother_V34_33k6_ECM256")
        if policies:
            self.policy_combo.addItems(policies)
        else:
            self.policy_combo.addItem("normal")
        self.output_edit.setText(str(Path("artifacts").resolve()))

    # ------------------------------------------------------------------ Helpers
    def _append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def _start_run(self) -> None:
        if self._worker is not None:
            return
        try:
            options = self._build_options()
        except ValueError as exc:
            QMessageBox.critical(self, "Validation error", str(exc))
            return
        self.log_view.clear()
        self._append_log("Preparing run with selected options…")
        self.run_button.setEnabled(False)
        self._status_label.setText("Run in progress…")
        self._loading_overlay.show_message("Running QAFAX verification…")
        self._worker = RunWorker(options, self._config_service)
        self._worker.progress.connect(self._append_log)
        self._worker.completed.connect(self._on_completed)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._cleanup_worker)
        self._worker.start()

    def _build_options(self) -> RunOptions:
        reference_path = self.reference_edit.text().strip()
        candidate_path = self.candidate_edit.text().strip()
        if not reference_path:
            raise ValueError("Reference document is required")
        if not candidate_path:
            raise ValueError("Candidate document is required")
        reference = Path(reference_path)
        candidate = Path(candidate_path)
        if not reference.exists():
            raise ValueError(f"Reference document not found: {reference}")
        if not candidate.exists():
            raise ValueError(f"Candidate document not found: {candidate}")

        output_dir = Path(self.output_edit.text().strip() or "artifacts")
        snmp_oids = [oid.strip() for oid in self.snmp_oids_edit.text().split(",") if oid.strip()]

        return RunOptions(
            reference=reference,
            candidate=candidate,
            profile=self.profile_combo.currentText() or "Brother_V34_33k6_ECM256",
            policy=self.policy_combo.currentText() or "normal",
            iterations=int(self.iterations_spin.value()),
            seed=int(self.seed_spin.value()),
            output_dir=output_dir,
            run_id=self.run_id_edit.text().strip() or "gui-run",
            path_mode=self.path_combo.currentText() or "digital",
            transport=self.transport_combo.currentText() or "sim",
            did=self.did_edit.text().strip() or None,
            pcfax_queue=self.pcfax_edit.text().strip() or None,
            ingest_dir=self.ingest_dir_edit.text().strip() or None,
            ingest_pattern=self.ingest_pattern_edit.text().strip() or "*",
            ingest_timeout=float(self.ingest_timeout_spin.value()),
            ingest_interval=float(self.ingest_interval_spin.value()),
            require_ocr=self.require_ocr_check.isChecked(),
            require_barcode=self.require_barcode_check.isChecked(),
            snmp_target=self.snmp_target_edit.text().strip() or None,
            snmp_community=self.snmp_community_edit.text().strip() or "public",
            snmp_oids=snmp_oids or list(DEFAULT_SNMP_OIDS),
            foip_config=Path(self.foip_config_edit.text().strip()) if self.foip_config_edit.text().strip() else None,
            t38_config=Path(self.t38_config_edit.text().strip()) if self.t38_config_edit.text().strip() else None,
            modem_config=Path(self.modem_config_edit.text().strip()) if self.modem_config_edit.text().strip() else None,
        )

    @Slot(object)
    def _on_completed(self, result: object) -> None:
        self._loading_overlay.hide_overlay()
        self._append_log("Run completed successfully.")
        try:
            run_dir = Path(getattr(result, "run_dir"))
        except (AttributeError, TypeError):
            self._last_result_dir = None
        else:
            self._last_result_dir = run_dir
            self._append_log(f"Artifacts written to {run_dir}")
        self.open_artifacts_button.setEnabled(self._last_result_dir is not None)
        self._status_label.setText("Run complete")

    @Slot(Exception)
    def _on_failed(self, error: Exception) -> None:
        self._loading_overlay.hide_overlay()
        self._append_log(f"Run failed: {error}")
        QMessageBox.critical(self, "Run failed", str(error))
        self._status_label.setText("Run failed")

    def _cleanup_worker(self) -> None:
        self.run_button.setEnabled(True)
        self._worker = None
        self._loading_overlay.hide_overlay()

    def _open_artifacts(self) -> None:
        if not self._last_result_dir:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_result_dir)))

    def _show_about(self) -> None:
        QMessageBox.information(
            self,
            "About QAFAX",
            (
                "QAFAX Desktop wraps the deterministic fax QA pipeline in a GUI.\n"
                "Runs orchestrate simulation, transport, verification, ingest, and reporting.\n"
                "Use the fields above to select inputs and optional connectors before executing."
            ),
        )

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if hasattr(self, "_loading_overlay"):
            self._loading_overlay.sync_geometry()


def launch() -> None:  # pragma: no cover - requires GUI loop
    """Entry point for launching the desktop GUI."""

    if QApplication is None:
        raise RuntimeError(
            "PySide6 is not installed. Install it with 'pip install PySide6' to use the GUI."
        ) from PySide6_IMPORT_ERROR

    app = QApplication.instance() or QApplication([])
    splash = WaveSplashScreen()
    splash.show()
    app.processEvents()

    window = MainWindow()  # type: ignore[call-arg]

    def show_main_window() -> None:
        splash.close()
        window.show()

    QTimer.singleShot(WaveSplashScreen.minimum_display_ms, show_main_window)
    app.exec()
