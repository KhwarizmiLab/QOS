#!/usr/bin/env python3
"""
QOS IBM Hardware Evaluation - Phase 10
Runs QOS scheduler on real IBM QPUs.
WARNING: This will consume IBM Quantum quota!
"""

import json
import yaml
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit

# Verify imports work
try:
    from qos.types.types import Qernel
    from qos.backends.types import QPU
    from settings.ibm_token import IBM_TOKEN, IBM_INSTANCE
    print("✓ All core imports successful")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

def load_real_backends():
    """Load real IBM backends from configuration."""
    backends_file = Path("evaluation/qpus_available_real.yml")

    if not backends_file.exists():
        print(f"✗ Backend config file not found: {backends_file}")
        return []

    with open(backends_file) as f:
        config = yaml.safe_load(f)

    backends = []

    # Parse backend configuration
    if "qpus" in config:
        for i, backend_config in enumerate(config["qpus"]):
            if not backend_config.get("active", True):
                continue

            qpu = QPU(
                id=i,
                name=backend_config.get("name", "unknown"),
                alias=backend_config.get("alias", f"ibm_{i}"),
                nqbits=backend_config.get("qubits", 0),
                provider="ibm_quantum",
                type="real_hardware",
                backend=None,  # Will be loaded via IBMProvider at runtime
            )
            backends.append(qpu)

    return backends

def create_test_jobs_for_real_hardware(num_jobs=4):
    """Create smaller test jobs suitable for real hardware."""
    jobs = []

    # Use smaller circuit sizes for real hardware due to decoherence
    circuit_sizes = [3, 4, 3, 5][:num_jobs]

    for i, size in enumerate(circuit_sizes):
        qc = QuantumCircuit(size, name=f"ibm_test_circuit_{i}")
        # Simple circuit for real hardware
        qc.h(0)
        for j in range(1, size):
            qc.cx(j-1, j)
        qc.measure_all()

        job = Qernel(qc=qc)
        job.id = i
        job.args["shots"] = 1024  # Lower shots for real hardware
        jobs.append(job)

    return jobs

def run_ibm_evaluation():
    """Run evaluation on IBM hardware."""
    print("\n" + "="*70)
    print("QOS IBM HARDWARE EVALUATION - PHASE 10")
    print("="*70)

    # Load configuration
    print("\n1. Loading IBM backend configuration...")
    backends = load_real_backends()

    if not backends:
        print("   ⚠ No active IBM backends found in configuration")
        print("   → Ensure evaluation/qpus_available_real.yml is configured")
        print("   → Check IBM_TOKEN and IBM_INSTANCE in settings/ibm_token.py")
        return None

    print(f"   ✓ Loaded {len(backends)} IBM backends")
    for b in backends[:3]:
        print(f"     - {b.name} ({b.nqbits} qubits)")

    # Create test jobs
    print("\n2. Creating test jobs for real hardware...")
    jobs = create_test_jobs_for_real_hardware(num_jobs=4)
    print(f"   ✓ Created {len(jobs)} test jobs")

    # Generate metadata
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "phase": "10_ibm_evaluation",
        "num_jobs": len(jobs),
        "num_backends": len(backends),
        "backend_names": [b.name for b in backends],
        "backend_aliases": [b.alias for b in backends],
        "job_circuit_sizes": [job.circuit.num_qubits for job in jobs],
        "backend_qubits": [b.nqbits for b in backends],
        "ibm_instance": IBM_INSTANCE,
        "status": "prepared",
        "note": "Real hardware evaluation prepared but not executed (requires active IBM session)",
    }

    # Save prepared metadata
    print("\n3. Saving evaluation metadata...")
    results_dir = Path("evaluation/data")
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = results_dir / f"results_ibm_{timestamp}.json"

    with open(results_file, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"   ✓ Metadata saved to {results_file}")

    print("\n" + "="*70)
    print("IBM HARDWARE EVALUATION - READY")
    print("="*70)
    print(f"Backends: {len(backends)}")
    print(f"Test Jobs: {len(jobs)}")
    print(f"Instance: {IBM_INSTANCE}")
    print(f"\nNOTE: To run actual hardware evaluation:")
    print("  1. Activate IBMProvider with valid credentials")
    print("  2. Submit jobs to backends")
    print("  3. Monitor job execution")
    print("  4. Collect and analyze results")
    print("="*70 + "\n")

    return results_file, metadata

if __name__ == "__main__":
    try:
        results_file, metadata = run_ibm_evaluation()
        if results_file:
            print("✓ Phase 10 (IBM Evaluation Setup) READY")
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
