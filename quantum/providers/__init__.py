# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
UMEROS Provider Abstraction Layer
=================================
Base classes and interfaces for quantum hardware providers.
"""

from .base import (
    BackendStatus,
    BackendTarget,
    BackendProperties,
    JobResult,
    BackendJob,
    BackendSession,
    BackendProvider,
    BackendTargetCoupling,
    GateSet,
    JobQueueMode,
)
from .braket_provider import (
    BraketProvider,
    BraketJob,
    BraketBackend,
    BraketError,
    BraketAPIError,
    BraketAuthError,
    BraketDeviceError,
    BraketJobError,
    BraketResultError,
)
from .ibm_provider import (
    IBMQuantumProvider,
    IBMQuantumJob,
    IBMQuantumBackend,
    IBMQuantumError,
    IBMAuthenticationError,
    IBMRatelimitError,
    IBMBackendNotFoundError,
    IBMJobError,
)
from .ionq_provider import (
    IonQProvider,
    IonQJob,
    IonQError,
    IonQAuthenticationError,
    IonQAPIError,
    IonQJobError,
)
from .rigetti_provider import (
    RigettiProvider,
    RigettiJob,
)

__all__ = [
    "BackendStatus",
    "BackendTarget",
    "BackendProperties",
    "JobResult",
    "BackendJob",
    "BackendSession",
    "BackendProvider",
    "BackendTargetCoupling",
    "GateSet",
    "JobQueueMode",
    # IBM
    "IBMQuantumProvider",
    "IBMQuantumJob",
    "IBMQuantumBackend",
    "IBMQuantumError",
    "IBMAuthenticationError",
    "IBMRatelimitError",
    "IBMBackendNotFoundError",
    "IBMJobError",
    # IonQ
    "IonQProvider",
    "IonQJob",
    "IonQError",
    "IonQAuthenticationError",
    "IonQAPIError",
    "IonQJobError",
    # Braket
    "BraketProvider",
    "BraketJob",
    "BraketBackend",
    "BraketError",
    "BraketAPIError",
    "BraketAuthError",
    "BraketDeviceError",
    "BraketJobError",
    "BraketResultError",
    # Rigetti
    "RigettiProvider",
    "RigettiJob",
]
