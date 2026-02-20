"""
Phase-level observability for the DRL-MOBTEST multi-phase training pipeline.
Tracks timing, inputs, outputs and events for each phase.
Exports to JSON for HTML report generation.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PhaseRecord:
    """Record for a single phase execution."""

    phase_id: str
    phase_name: str
    start_time: float = 0.0
    end_time: float | None = None
    duration: float | None = None
    status: str = "pending"  # pending | running | completed | failed
    inputs: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    error: str | None = None


class PhaseObserver:
    """
    Observability hub for the multi-phase training pipeline.
    Each phase calls begin/end on this object to record timing and results.
    Sub-events are recorded with record_event().
    All data can be exported to JSON with save().
    """

    def __init__(self, run_id: str, output_path: Path):
        self.run_id = run_id
        self.output_path = Path(output_path)
        self.output_path.mkdir(parents=True, exist_ok=True)
        self.records: dict[str, PhaseRecord] = {}

    def begin_phase(self, phase_id: str, phase_name: str, inputs: dict | None = None) -> None:
        """Mark the start of a phase."""
        record = PhaseRecord(
            phase_id=phase_id,
            phase_name=phase_name,
            start_time=time.time(),
            status="running",
            inputs=inputs or {},
        )
        self.records[phase_id] = record
        logger.info("Phase %s (%s) started", phase_id, phase_name)

    def end_phase(self, phase_id: str, outputs: dict | None = None) -> None:
        """Mark the successful completion of a phase."""
        if phase_id not in self.records:
            logger.warning("end_phase called for unknown phase %s", phase_id)
            return
        record = self.records[phase_id]
        record.end_time = time.time()
        record.duration = record.end_time - record.start_time
        record.status = "completed"
        record.outputs = outputs or {}
        logger.info(
            "Phase %s (%s) completed in %.1fs",
            phase_id,
            record.phase_name,
            record.duration,
        )

    def fail_phase(self, phase_id: str, error: Exception) -> None:
        """Mark a phase as failed."""
        if phase_id not in self.records:
            logger.warning("fail_phase called for unknown phase %s", phase_id)
            return
        record = self.records[phase_id]
        record.end_time = time.time()
        record.duration = record.end_time - record.start_time
        record.status = "failed"
        record.error = str(error)
        logger.error("Phase %s failed: %s", phase_id, error)

    def record_event(self, phase_id: str, event_type: str, data: dict | None = None) -> None:
        """Record a sub-event within a phase."""
        if phase_id not in self.records:
            logger.warning("record_event called for unknown phase %s", phase_id)
            return
        event = {
            "timestamp": time.time(),
            "event_type": event_type,
            "data": data or {},
        }
        self.records[phase_id].events.append(event)

    def get_summary(self) -> dict[str, Any]:
        """Return full summary dict for JSON serialization."""
        return {
            "run_id": self.run_id,
            "phases": {
                pid: {
                    "phase_id": r.phase_id,
                    "phase_name": r.phase_name,
                    "status": r.status,
                    "duration": r.duration,
                    "start_time": r.start_time,
                    "end_time": r.end_time,
                    "inputs": r.inputs,
                    "outputs": r.outputs,
                    "events_count": len(r.events),
                    "events": r.events,
                    "error": r.error,
                }
                for pid, r in self.records.items()
            },
        }

    def get_phase_durations(self) -> dict[str, float]:
        """Return {phase_id: duration_seconds} for completed phases."""
        return {pid: r.duration for pid, r in self.records.items() if r.duration is not None}

    def save(self, filename: str | None = None) -> Path:
        """Serialize all PhaseRecord objects to JSON."""
        if filename is None:
            filename = f"phase_report_{self.run_id}.json"
        filepath = self.output_path / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.get_summary(), f, indent=2, default=str)
        logger.info("Phase report saved: %s", filepath)
        return filepath
