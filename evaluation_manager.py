#!/usr/bin/env python3
"""
Evaluation Results Manager
Handles organization of experiment results in evaluations/ directory.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Literal, Tuple


class EvaluationManager:
    """Manages evaluation result directories and metadata."""

    EVALUATIONS_ROOT = Path("evaluations")
    PAPER_RESULTS_DIR = EVALUATIONS_ROOT / "paper_results"

    def __init__(self):
        """Initialize the evaluation manager."""
        self.ensure_structure()

    @classmethod
    def ensure_structure(cls):
        """Ensure evaluations/ directory structure exists."""
        cls.EVALUATIONS_ROOT.mkdir(exist_ok=True)
        cls.PAPER_RESULTS_DIR.mkdir(exist_ok=True)

    @classmethod
    def get_next_counter(cls, exp_type: Literal["sim", "ibm"]) -> int:
        """
        Get the next counter for a new experiment directory.

        Args:
            exp_type: "sim" or "ibm"

        Returns:
            Next integer counter (1-indexed)
        """
        pattern = rf"^{exp_type}_(\d+)_"
        existing = []

        for dir_path in cls.EVALUATIONS_ROOT.iterdir():
            if not dir_path.is_dir():
                continue
            match = re.match(pattern, dir_path.name)
            if match:
                existing.append(int(match.group(1)))

        return max(existing) if existing else 0 + 1

    @classmethod
    def create_results_directory(
        cls, exp_type: Literal["sim", "ibm"]
    ) -> Path:
        """
        Create a new results directory for an experiment run.

        Args:
            exp_type: "sim" or "ibm"

        Returns:
            Path to the new results directory
        """
        counter = cls.get_next_counter(exp_type)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dir_name = f"{exp_type}_{counter:03d}_{timestamp}_results"
        results_dir = cls.EVALUATIONS_ROOT / dir_name

        # Create subdirectories
        results_dir.mkdir(parents=True, exist_ok=True)
        (results_dir / "data").mkdir(exist_ok=True)
        (results_dir / "plots").mkdir(exist_ok=True)

        return results_dir

    @classmethod
    def save_metadata(
        cls,
        results_dir: Path,
        metadata: dict,
    ) -> Path:
        """
        Save experiment metadata to results directory.

        Args:
            results_dir: Path to results directory
            metadata: Metadata dictionary

        Returns:
            Path to metadata.json
        """
        metadata_file = results_dir / "metadata.json"

        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        return metadata_file

    @classmethod
    def load_metadata(cls, results_dir: Path) -> dict:
        """
        Load metadata from a results directory.

        Args:
            results_dir: Path to results directory

        Returns:
            Metadata dictionary
        """
        metadata_file = results_dir / "metadata.json"

        if not metadata_file.exists():
            return {}

        with open(metadata_file) as f:
            return json.load(f)

    @classmethod
    def list_experiments(
        cls, exp_type: Literal["sim", "ibm", "all"] = "all"
    ) -> list:
        """
        List all experiments in chronological order.

        Args:
            exp_type: "sim", "ibm", or "all"

        Returns:
            List of (counter, timestamp, path, metadata) tuples
        """
        experiments = []

        for dir_path in sorted(cls.EVALUATIONS_ROOT.iterdir()):
            if not dir_path.is_dir():
                continue

            # Skip paper_results
            if dir_path.name == "paper_results":
                continue

            # Parse directory name
            match = re.match(
                r"^(sim|ibm)_(\d+)_(\d{8}_\d{6})_results$",
                dir_path.name,
            )
            if not match:
                continue

            dir_type, counter, timestamp = match.groups()

            # Filter by type if specified
            if exp_type != "all" and dir_type != exp_type:
                continue

            # Load metadata
            metadata = cls.load_metadata(dir_path)

            experiments.append({
                "type": dir_type,
                "counter": int(counter),
                "timestamp": timestamp,
                "path": dir_path,
                "metadata": metadata,
                "dir_name": dir_path.name,
            })

        # Sort by counter
        return sorted(experiments, key=lambda x: (x["type"], x["counter"]))

    @classmethod
    def get_latest_experiment(cls, exp_type: Literal["sim", "ibm"]) -> dict | None:
        """
        Get the latest experiment of a given type.

        Args:
            exp_type: "sim" or "ibm"

        Returns:
            Experiment dict or None if not found
        """
        experiments = cls.list_experiments(exp_type)
        return experiments[-1] if experiments else None

    @classmethod
    def print_summary(cls):
        """Print a summary of all experiments."""
        experiments = cls.list_experiments()

        print("\n" + "="*70)
        print("EVALUATION EXPERIMENTS SUMMARY")
        print("="*70)

        if not experiments:
            print("No experiments found.")
            return

        for exp in experiments:
            status = exp["metadata"].get("status", "unknown")
            num_jobs = exp["metadata"].get("num_jobs", "?")
            num_backends = exp["metadata"].get("num_backends", "?")

            print(
                f"\n{exp['dir_name']}\n"
                f"  Type: {exp['type'].upper()}\n"
                f"  Jobs: {num_jobs} | Backends: {num_backends}\n"
                f"  Status: {status}\n"
            )

        print("="*70 + "\n")


if __name__ == "__main__":
    # Example usage
    manager = EvaluationManager()

    # List experiments
    manager.print_summary()

    # Get latest simulator run
    latest_sim = manager.get_latest_experiment("sim")
    if latest_sim:
        print(f"Latest simulator run: {latest_sim['dir_name']}")
