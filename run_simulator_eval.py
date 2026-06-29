#!/usr/bin/env python3
"""
QOS Simulator Evaluation - Paper Validation
Runs QOS scheduler (NSGA-II) on fake Qiskit backends and compares Pareto front
metrics to paper results (evaluations/paper_results/).
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from timeit import default_timer as timer

import numpy as np
from qiskit import QuantumCircuit
from qiskit.providers.fake_provider import (
    Fake5QV1, Fake20QV1, Fake27QPulseV1
)
from qiskit.transpiler import CouplingMap

try:
    from src.scheduler.base_scheduler import SchedulingJob
    from src.execution_time.base_estimator import BaseEstimator
    from qos.scheduler.multi_objective_scheduler import MultiObjectiveScheduler
    from evaluation_manager import EvaluationManager
    print("✓ All core imports successful")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)


class SimpleEstimator(BaseEstimator):
    """
    Depth-based execution time estimator that requires no trained model.
    Estimates time as (circuit_depth * 1µs * shots) per circuit.
    Absolute values aren't critical — NSGA-II only needs relative ordering.
    """

    def estimate_execution_time(self, circuits, backend, **kwargs) -> float:
        shots = kwargs.get("shots", 4000)
        total = sum(c.depth() * 1e-6 for c in circuits)
        return total * shots


# ---------------------------------------------------------------------------
# Backend setup — 4 fake backends covering different qubit counts.
# Scheduler needs actual Qiskit Backend objects (not QPU wrappers) because
# it calls .num_qubits, .properties(), .coupling_map, .operation_names, etc.
# ---------------------------------------------------------------------------

BACKEND_CONFIGS = [
    ("fake_kolkata",   Fake27QPulseV1),
    ("fake_cairo",     Fake20QV1),
    ("fake_lagos",     Fake20QV1),
    ("fake_nairobi",   Fake5QV1),
]


def _make_v2_compat(v1_cls, display_name):
    """
    Subclass a V1 FakeBackend to expose the V2 API expected by the scheduler:
    .num_qubits, .operation_names, .coupling_map (as CouplingMap object).
    V1 backends already have .properties(), .status().pending_jobs, and
    isinstance(b, FakeBackend) → True, so transpile() works unchanged.
    """
    class _Compat(v1_cls):
        @property
        def num_qubits(self):
            return self.configuration().n_qubits

        @property
        def operation_names(self):
            return self.configuration().basis_gates

        @property
        def coupling_map(self):
            return CouplingMap(self.configuration().coupling_map)

    _Compat.__name__ = display_name
    return _Compat


def create_backends():
    """Return (qiskit_backends, display_info) for BACKEND_CONFIGS."""
    qiskit_backends = []
    display_info = []
    for name, cls in BACKEND_CONFIGS:
        compat_cls = _make_v2_compat(cls, name)
        backend = compat_cls()
        qiskit_backends.append(backend)
        display_info.append({"name": name, "nqbits": backend.num_qubits})
    return qiskit_backends, display_info


def load_qpu_load_data():
    path = Path("evaluations/paper_results/QPU_load.json")
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


# ---------------------------------------------------------------------------
# Job creation — SchedulingJob is what MultiObjectiveScheduler expects.
# SchedulingJob(circuits: list[QuantumCircuit], shots: int)
# NOT Qernel — Qernel uses .circuit (singular) and .args["shots"].
# ---------------------------------------------------------------------------

NUM_JOBS = 100         # paper scale: 100 jobs
TRANSPILE_COUNT = 10   # paper scale: 10 transpilations per circuit


def create_jobs(num=NUM_JOBS) -> list[SchedulingJob]:
    np.random.seed(42)
    sizes = np.random.randint(5, 16, num)
    jobs = []
    for i in range(num):
        sz = int(sizes[i])
        qc = QuantumCircuit(sz, name=f"qaoa_{i}")
        qc.h(range(sz))
        for j in range(0, sz - 1, 2):
            qc.cx(j, j + 1)
        qc.ry(0.5, range(sz))
        qc.measure_all()
        jobs.append(SchedulingJob(circuits=[qc], shots=8192))
    return jobs


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def load_paper_reference():
    """Load one paper result for comparison (metadata_balanced.json)."""
    ref_path = Path("evaluations/paper_results/metadata_balanced.json")
    if ref_path.exists():
        with open(ref_path) as f:
            return json.load(f)
    return None


def run_evaluation():
    print("\n" + "=" * 70)
    print("QOS SIMULATOR EVALUATION — PAPER VALIDATION")
    print("=" * 70)

    # 1. Backends
    print(f"\n1. Creating {len(BACKEND_CONFIGS)} fake backends...")
    qiskit_backends, display_info = create_backends()
    for d in display_info:
        print(f"      - {d['name']} ({d['nqbits']} qubits)")

    # 2. QPU load
    print("\n2. Loading QPU load data...")
    qpu_load = load_qpu_load_data()
    print(f"   ✓ {len(qpu_load)} QPU load entries")

    # 3. Jobs
    print(f"\n3. Creating {NUM_JOBS} SchedulingJob objects...")
    jobs = create_jobs(NUM_JOBS)
    sizes = [j.circuits[0].num_qubits for j in jobs]
    print(f"   ✓ Circuit sizes: min={min(sizes)}, max={max(sizes)}, mean={np.mean(sizes):.1f}")

    # 4. Results dir
    print("\n4. Setting up results directory...")
    manager = EvaluationManager()
    results_dir = manager.create_results_directory("sim")
    print(f"   ✓ {results_dir}")

    # 5. Schedule
    print(f"\n5. Running MultiObjectiveScheduler (NSGA-II, pop=100, {TRANSPILE_COUNT} transpilations)...")
    print("   (This may take a few minutes...)")

    results_metadata: dict = {
        "timestamp": datetime.now().isoformat(),
        "num_jobs": NUM_JOBS,
        "num_backends": len(qiskit_backends),
        "backend_names": [d["name"] for d in display_info],
        "backend_qubits": [d["nqbits"] for d in display_info],
        "job_circuit_sizes": sizes,
        "transpilation_count": TRANSPILE_COUNT,
    }

    try:
        # MultiObjectiveScheduler.__init__ params:
        #   transpilation_count, transpilation_level, algorithm, estimator, problem_type
        # (NOT backend_list / waiting_time_injector / initial_layout_method)
        scheduler = MultiObjectiveScheduler(
            transpilation_count=TRANSPILE_COUNT,
            estimator=SimpleEstimator(),
        )

        t0 = timer()
        # schedule() returns tuple: (assignments, rejected_jobs, metadata_dict)
        assignments, rejected, sched_meta = scheduler.schedule(
            jobs=jobs,
            backends=qiskit_backends,
            weights=[0.5, 0.5],
        )
        elapsed = timer() - t0

        print(f"   ✓ Scheduling completed in {elapsed:.1f}s")
        print(f"   ✓ Assigned: {len(assignments)}, Rejected: {len(rejected)}")

        # Pareto front objective arrays from scheduler metadata
        mean_error = np.array(sched_meta.get("mean_error", []))        # 1-fidelity per Pareto solution
        mean_wt    = np.array(sched_meta.get("mean_waiting_time", []))  # waiting time per Pareto solution

        results_metadata.update({
            "status": "completed",
            "scheduling_time_seconds": elapsed,
            "num_assigned": len(assignments),
            "num_rejected": len(rejected),
            "pareto_front_size": len(mean_error),
            "mean_fidelity": float(np.mean(1.0 - mean_error)) if len(mean_error) else None,
            "mean_waiting_time": float(np.mean(mean_wt)) if len(mean_wt) else None,
            "transpilation_time": sched_meta.get("transpilation_time"),
            "estimation_time": sched_meta.get("estimation_time"),
            "optimization_time": sched_meta.get("optimization_time"),
            "mcdm_time": sched_meta.get("mcdm_time"),
            "schedule_generation_time": sched_meta.get("schedule_generation_time"),
            "solution_index": sched_meta.get("solution_index"),
            "waiting_time_90p": sched_meta.get("waiting_time_90_percentile"),
            "waiting_time_95p": sched_meta.get("waiting_time_95_percentile"),
            "fidelity_90p": sched_meta.get("fidelity_90_percentile"),
            "fidelity_95p": sched_meta.get("fidelity_95_percentile"),
        })

    except Exception as e:
        print(f"   ✗ Scheduler error: {e}")
        import traceback; traceback.print_exc()
        results_metadata["status"] = "failed"
        results_metadata["error"] = str(e)
        mean_error = np.array([])
        mean_wt = np.array([])

    # 6. Save
    print("\n6. Saving results...")
    results_file = results_dir / "data" / "results.json"
    with open(results_file, "w") as f:
        json.dump(results_metadata, f, indent=2)
    print(f"   ✓ {results_file}")

    experiment_metadata = {
        "experiment_id": f"sim_{manager.get_next_counter('sim') - 1:03d}",
        "timestamp": datetime.now().isoformat(),
        "type": "simulator",
        "description": f"{NUM_JOBS}-job paper validation ({len(BACKEND_CONFIGS)} fake backends)",
        "config": {"num_jobs": NUM_JOBS, "num_backends": len(qiskit_backends), "weights": [0.5, 0.5]},
        "results_file": "data/results.json",
        "plots": [],
        "status": results_metadata["status"],
    }
    manager.save_metadata(results_dir, experiment_metadata)

    # 7. Compare to paper
    print("\n" + "=" * 70)
    print("PAPER COMPARISON")
    print("=" * 70)
    print("Paper results (from evaluations/paper_results/):")
    print("  Mean error range:        0.162 – 0.220  →  Fidelity 0.780 – 0.838")
    print("  Mean waiting time range: 243 – 1174 s")
    print()

    ref = load_paper_reference()
    if ref:
        paper_err_vals = ref.get("mean_error", [])
        paper_wt_vals  = ref.get("mean_waiting_time", [])
        if paper_err_vals:
            print(f"  Paper ref (balanced):    error {np.mean(paper_err_vals):.3f}, wt {np.mean(paper_wt_vals):.1f}s")

    if results_metadata["status"] == "completed" and len(mean_error):
        our_fidelity = float(np.mean(1.0 - mean_error))
        our_wt       = float(np.mean(mean_wt))
        print(f"  Our results:             fidelity {our_fidelity:.3f}, wt {our_wt:.1f}s")
        print(f"  Pareto front size:       {len(mean_error)}")

        fid_in_range = 0.70 <= our_fidelity <= 0.95
        print(f"\n  Fidelity in plausible range [0.70, 0.95]: {'✓ YES' if fid_in_range else '✗ NO'}")
    else:
        print("  Our results: FAILED — see error above")

    print(f"\nResults dir: {results_dir}")
    print("=" * 70 + "\n")

    return results_dir, results_metadata


if __name__ == "__main__":
    try:
        results_dir, metadata = run_evaluation()
        status = metadata.get("status", "unknown")
        if status == "completed":
            print("✓ Evaluation COMPLETE")
            sys.exit(0)
        else:
            print(f"✗ Evaluation ended with status: {status}")
            sys.exit(1)
    except Exception as e:
        import traceback; traceback.print_exc()
        sys.exit(1)
