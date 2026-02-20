"""
DRL-MOBTEST multi-phase training pipeline.

Phases:
  0a - APK Manifest Parser
  0b - Semantic Crawling + LLM Annotation
  0c - Replay Memory Warm-up
  1  - RL Training with Coverage Reward (in training/runner.py)
  2  - Enriched CrewAI Transcription
"""

from rlmobtest.phases.phase_0a_manifest import ManifestResult, parse_manifest
from rlmobtest.phases.phase_0b_crawl import ActivitySnapshot, CrawlResult, run_semantic_crawl
from rlmobtest.phases.phase_0c_warmup import WarmupResult, warmup_replay_memory
from rlmobtest.phases.phase_2_transcription import TranscriptionResult, run_enriched_transcription

__all__ = [
    "ManifestResult",
    "parse_manifest",
    "ActivitySnapshot",
    "CrawlResult",
    "run_semantic_crawl",
    "WarmupResult",
    "warmup_replay_memory",
    "TranscriptionResult",
    "run_enriched_transcription",
]
