"""Model checkpoint save/load management."""

from datetime import datetime
from pathlib import Path

import torch

from rlmobtest.training.device import device


class ModelCheckpoint:
    """Gerenciador de checkpoints."""

    def __init__(self, save_dir: Path):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def save(self, model, optimizer, metrics, episode, steps_done, filename=None):
        if filename is None:
            filename = f"checkpoint_ep{episode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pt"

        checkpoint = {
            "episode": episode,
            "steps_done": steps_done,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "metrics": {
                "episode_rewards": metrics.episode_rewards,
                "episode_lengths": metrics.episode_lengths,
            },
            "timestamp": datetime.now().isoformat(),
            "feature_size": getattr(model, "_feature_size", None),
        }

        filepath = self.save_dir / filename
        torch.save(checkpoint, filepath)
        print(f"Checkpoint saved: {filepath.name}")
        return filepath

    def load(self, filepath, model, optimizer):
        checkpoint = torch.load(filepath, map_location=device)

        # Initialize lazy layers before loading state dict (for DuelingDQN)
        if hasattr(model, "_initialize_fc") and model.value_stream is None:
            feature_size = checkpoint.get("feature_size")
            if feature_size is None:
                state_dict = checkpoint["model_state_dict"]
                if "value_stream.0.weight" in state_dict:
                    feature_size = state_dict["value_stream.0.weight"].shape[1]
            if feature_size is not None:
                model._feature_size = feature_size
                model._initialize_fc(feature_size)

        model.load_state_dict(checkpoint["model_state_dict"])
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        print(f"Checkpoint loaded: {filepath}")
        return checkpoint["episode"], checkpoint["steps_done"]
