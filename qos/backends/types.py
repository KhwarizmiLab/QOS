"""QPU (Quantum Processing Unit) type definition."""

from dataclasses import dataclass, field
from typing import List, Any, Optional
from qiskit.providers import Backend


@dataclass
class QPU:
    """Quantum Processing Unit metadata wrapper for QOS scheduling."""

    id: int = 0
    name: str = ""
    alias: str = ""
    nqbits: int = 0
    provider: str = "qiskit"
    type: str = "simulator"
    local_queue: List[tuple] = field(default_factory=list)
    backend: Optional[Backend] = None
    args: dict = field(default_factory=dict)

    def __post_init__(self):
        """Set alias from name if not provided."""
        if not self.alias and self.name:
            self.alias = self.name.lower().replace(" ", "_")
