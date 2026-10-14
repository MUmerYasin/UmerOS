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
UmerOS /kernel — ONNX predictor example  [FUTURE]
==================================================
Reference snippet showing a lightweight, local-first ONNX inference endpoint so
that routing layers can offload sub-tasks to local hardware (CPU/GPU) without
the privacy and latency overhead of cloud APIs.

.. note:: This is a documentation/reference example, NOT part of the kernel.
   ``onnxruntime`` is imported lazily inside the class so that importing this
   module has no third-party dependency and no side effects.
"""

from __future__ import annotations

import logging

log = logging.getLogger("UmerOS.Kernel.OnnxExample")


class OnnxPredictorStub:
    """Minimal ONNX Runtime predictor wrapper (requires ``onnxruntime``)."""

    def __init__(self, model_path: str):
        import onnxruntime as ort

        self.session = ort.InferenceSession(model_path)
        self.input_name = self.session.get_inputs()[0].name

    def predict(self, input_tensor):
        """Run inference on the provided tensor and return the raw output."""
        return self.session.run(None, {self.input_name: input_tensor})
