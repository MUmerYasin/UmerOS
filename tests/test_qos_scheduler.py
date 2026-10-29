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
Unit tests for UmerOS Deterministic Latency QoS Engine.

Tests:
- Default QoS assignment on Task (TaskQoS.UTILITY).
- QoS-weighted schedule_score calculation.
- USER_INTERACTIVE tasks get priority boost over BACKGROUND tasks.
- Frame drop telemetry reporting triggers throttling.
- Dynamic throttling factor suppresses BACKGROUND tasks during frame drops.
- QoSManager statistics and metrics reset.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kernel.qos import QoSManager, TaskQoS, qos_manager
from kernel.scheduler import HybridScheduler, Task


class TestDeterministicLatencyQoS(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        qos_manager.reset_metrics()

    def tearDown(self):
        qos_manager.reset_metrics()

    def test_default_qos_is_utility(self):
        task = Task(pid=1, name="default_task", priority=0.5)
        self.assertEqual(task.qos, TaskQoS.UTILITY)

    def test_qos_weight_boosts_interactive_score(self):
        # Two tasks with identical priority and CPU time
        bg_task = Task(pid=10, name="quantum_sim", priority=0.8, qos=TaskQoS.BACKGROUND)
        ui_task = Task(pid=11, name="shell_input", priority=0.8, qos=TaskQoS.USER_INTERACTIVE)

        self.assertGreater(ui_task.schedule_score, bg_task.schedule_score)

        # UI task score is 10x the background task score (100 vs 10 weight)
        ratio = ui_task.schedule_score / bg_task.schedule_score
        self.assertAlmostEqual(ratio, 10.0, places=1)

    def test_frame_drop_telemetry_triggers_throttling(self):
        mgr = QoSManager()
        self.assertFalse(mgr.is_throttled())

        # Frame completed within 16ms deadline -> not throttled
        is_throttled = mgr.record_frame_metric(render_time_ms=12.5, dropped=False)
        self.assertFalse(is_throttled)

        # Frame missed deadline (28.4ms) -> triggers throttling
        is_throttled = mgr.record_frame_metric(render_time_ms=28.4, dropped=True)
        self.assertTrue(is_throttled)
        self.assertTrue(mgr.is_throttled())

        stats = mgr.stats()
        self.assertEqual(stats["dropped_frames_count"], 1)
        self.assertEqual(stats["total_frames_reported"], 2)

    def test_throttle_factor_reduces_background_score(self):
        bg_task = Task(pid=20, name="batch_job", priority=0.5, qos=TaskQoS.BACKGROUND)
        ui_task = Task(pid=21, name="touch_event", priority=0.5, qos=TaskQoS.USER_INTERACTIVE)

        score_before_throttle = bg_task.schedule_score
        ui_score_before = ui_task.schedule_score

        # Trigger frame drop in global qos_manager
        qos_manager.record_frame_metric(render_time_ms=35.0, dropped=True)

        score_after_throttle = bg_task.schedule_score
        ui_score_after = ui_task.schedule_score

        # UI score remains completely un-throttled
        self.assertAlmostEqual(ui_score_before, ui_score_after)

        # Background score is significantly suppressed (throttle factor 0.1)
        self.assertLess(score_after_throttle, score_before_throttle)
        self.assertAlmostEqual(score_after_throttle, score_before_throttle * 0.1, places=2)

    async def test_scheduler_selection_prefers_interactive_under_load(self):
        scheduler = HybridScheduler()
        t_bg = Task(pid=101, name="heavy_quantum_batch", priority=0.9, qos=TaskQoS.BACKGROUND)
        t_ui = Task(pid=102, name="flutter_dock_click", priority=0.5, qos=TaskQoS.USER_INTERACTIVE)

        await scheduler.add_task(t_bg)
        await scheduler.add_task(t_ui)

        # Even though t_bg has higher base priority (0.9 vs 0.5), t_ui wins because of QoS (100 vs 10)
        selected = await scheduler.tick()
        self.assertIsNotNone(selected)
        self.assertEqual(selected.pid, 102)


if __name__ == "__main__":
    unittest.main()
