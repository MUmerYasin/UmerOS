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

"""H250 - the "AI firewall" was a toy, and it failed open.

The row was: ``security/firewall.py`` ``AIFirewall.analyze_packet`` only blocks
``dst_port == 22`` by source IP, there is no inspection/state/egress filtering,
``add_rule`` appends to a list nothing reads, and the "AI-driven" claim is
false. The provenance ("merged from Deepseek code") was unsubstantiated.

Drift-recon found the logic bug the row did not name: the method recorded the
blocked source and then **allowed every later packet from it**, SSH included -
it failed open one packet after doing its job. That is pinned first here,
because it is the part that made the module worse than useless.
"""
from __future__ import annotations

import ast
import pathlib
import unittest

import security.firewall as fwmod
from security.firewall import AIFirewall

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
MODULE_PATH = PROJECT_ROOT / "security" / "firewall.py"


# ---------------------------------------------------------------------------
# The fail-open bug
# ---------------------------------------------------------------------------

class TestDropIsSticky(unittest.TestCase):
    """The old code blocked one packet, then allowed the rest of the flow."""

    def setUp(self):
        self.fw = AIFirewall()

    def test_every_packet_of_a_denied_flow_is_dropped(self):
        verdicts = [self.fw.analyze_packet("1.2.3.4", 22) for _ in range(5)]
        self.assertEqual(
            verdicts,
            [AIFirewall.DROP] * 5,
            "the old implementation returned DROP once and ALLOW afterwards",
        )

    def test_a_blocked_source_is_dropped_on_other_ports_too(self):
        self.assertEqual(self.fw.analyze_packet("1.2.3.4", 22), AIFirewall.DROP)
        self.assertEqual(self.fw.analyze_packet("1.2.3.4", 443), AIFirewall.DROP)

    def test_blocking_one_source_does_not_block_another(self):
        self.fw.analyze_packet("1.2.3.4", 22)
        self.assertEqual(self.fw.analyze_packet("5.6.7.8", 443), AIFirewall.ALLOW)
        self.assertFalse(self.fw.is_blocked("5.6.7.8"))

    def test_is_blocked_reports_the_recorded_source(self):
        self.assertFalse(self.fw.is_blocked("1.2.3.4"))
        self.fw.analyze_packet("1.2.3.4", 22)
        self.assertTrue(self.fw.is_blocked("1.2.3.4"))
        self.assertIn("1.2.3.4", self.fw.blocked_ips)

    def test_unblock_lifts_the_block(self):
        self.fw.analyze_packet("1.2.3.4", 22)
        self.assertTrue(self.fw.unblock("1.2.3.4"))
        self.assertFalse(self.fw.is_blocked("1.2.3.4"))
        self.assertEqual(self.fw.analyze_packet("1.2.3.4", 443), AIFirewall.ALLOW)

    def test_unblock_of_a_source_that_was_never_blocked_returns_false(self):
        self.assertFalse(self.fw.unblock("9.9.9.9"))


# ---------------------------------------------------------------------------
# Rules are consulted (they used to be a list nothing read)
# ---------------------------------------------------------------------------

class TestRulesAreConsulted(unittest.TestCase):

    def test_an_allow_rule_overrides_the_heuristic(self):
        fw = AIFirewall()
        fw.add_rule(("10.0.0.5", 22, "ALLOW"))
        self.assertEqual(fw.analyze_packet("10.0.0.5", 22), AIFirewall.ALLOW)
        self.assertEqual(fw.analyze_packet("10.0.0.6", 22), AIFirewall.DROP)

    def test_a_drop_rule_works_on_a_port_the_heuristic_ignores(self):
        fw = AIFirewall()
        fw.add_rule(("*", 8080, "DROP"))
        self.assertEqual(fw.analyze_packet("9.9.9.9", 8080), AIFirewall.DROP)
        self.assertTrue(fw.is_blocked("9.9.9.9"))

    def test_a_wildcard_source_rule_matches_any_source(self):
        fw = AIFirewall()
        fw.add_rule(("*", 25, "DROP"))
        for src in ("1.1.1.1", "2.2.2.2", "3.3.3.3"):
            self.assertEqual(fw.analyze_packet(src, 25), AIFirewall.DROP)

    def test_a_wildcard_port_rule_matches_any_port(self):
        fw = AIFirewall()
        fw.add_rule(("4.4.4.4", "*", "ALLOW"))
        for port in (22, 443, 8080):
            self.assertEqual(fw.analyze_packet("4.4.4.4", port), AIFirewall.ALLOW)

    def test_first_matching_rule_wins(self):
        fw = AIFirewall()
        fw.add_rule(("7.7.7.7", 22, "ALLOW"))
        fw.add_rule(("*", 22, "DROP"))
        self.assertEqual(fw.analyze_packet("7.7.7.7", 22), AIFirewall.ALLOW)

        fw2 = AIFirewall()
        fw2.add_rule(("*", 22, "DROP"))
        fw2.add_rule(("7.7.7.7", 22, "ALLOW"))
        self.assertEqual(
            fw2.analyze_packet("7.7.7.7", 22),
            AIFirewall.DROP,
            "a rule later in the list must not override an earlier match",
        )

    def test_clear_rules_empties_the_table(self):
        fw = AIFirewall()
        fw.add_rule(("1.1.1.1", 22, "ALLOW"))
        fw.add_rule(("*", 25, "DROP"))
        self.assertEqual(fw.clear_rules(), 2)
        self.assertEqual(fw.rules, [])
        self.assertEqual(fw.analyze_packet("1.1.1.1", 22), AIFirewall.DROP)


class TestRuleValidation(unittest.TestCase):

    def test_a_malformed_rule_is_refused(self):
        fw = AIFirewall()
        bad_rules = [
            ("1.2.3.4", 22),                     # too short
            ("1.2.3.4", 22, "ALLOW", "extra"),   # too long
            "",                                  # a bare string
            "notarule",
            None,
            (None, 22, "DROP"),                  # ip not a str
            ("", 22, "DROP"),                    # empty ip
            ("1.2.3.4", 99999, "DROP"),          # port out of range
            ("1.2.3.4", -1, "DROP"),
            ("1.2.3.4", True, "DROP"),           # bool is not a port
            ("1.2.3.4", "22", "DROP"),           # numeric string is not a port
            ("1.2.3.4", 22, "MAYBE"),            # unknown action
            ("1.2.3.4", 22, None),
        ]
        for rule in bad_rules:
            with self.subTest(rule=repr(rule)):
                with self.assertRaises(ValueError):
                    fw.add_rule(rule)
        self.assertEqual(fw.rules, [], "a refused rule must not be stored")

    def test_a_valid_rule_is_stored_in_normalised_form(self):
        fw = AIFirewall()
        stored = fw.add_rule(("1.2.3.4", 22, "drop"))
        self.assertEqual(stored, ("1.2.3.4", 22, "DROP"))
        self.assertEqual(fw.rules, [("1.2.3.4", 22, "DROP")])

    def test_a_list_is_accepted_as_well_as_a_tuple(self):
        fw = AIFirewall()
        self.assertEqual(fw.add_rule(["1.2.3.4", "*", "allow"]), ("1.2.3.4", "*", "ALLOW"))


# ---------------------------------------------------------------------------
# The heuristic itself
# ---------------------------------------------------------------------------

class TestHeuristic(unittest.TestCase):

    def test_only_the_configured_ports_are_denied_by_default(self):
        fw = AIFirewall()
        self.assertEqual(fw.analyze_packet("1.1.1.1", 22), AIFirewall.DROP)
        self.assertEqual(fw.analyze_packet("2.2.2.2", 443), AIFirewall.ALLOW)
        self.assertEqual(fw.analyze_packet("3.3.3.3", 80), AIFirewall.ALLOW)

    def test_the_heuristic_ports_are_configurable(self):
        fw = AIFirewall(heuristic_ports=[23, 3389])
        self.assertEqual(fw.analyze_packet("1.1.1.1", 23), AIFirewall.DROP)
        self.assertEqual(fw.analyze_packet("2.2.2.2", 3389), AIFirewall.DROP)
        self.assertEqual(
            fw.analyze_packet("3.3.3.3", 22),
            AIFirewall.ALLOW,
            "port 22 is only special because it is in the default set",
        )

    def test_an_empty_heuristic_allows_everything_unless_a_rule_says_otherwise(self):
        fw = AIFirewall(heuristic_ports=[])
        self.assertEqual(fw.analyze_packet("1.1.1.1", 22), AIFirewall.ALLOW)


# ---------------------------------------------------------------------------
# The labels match the code
# ---------------------------------------------------------------------------

class TestLabelsMatchTheCode(unittest.TestCase):

    def test_the_module_says_what_it_is_not(self):
        doc = fwmod.__doc__ or ""
        flat = " ".join(doc.split())  # docstrings are line-wrapped
        self.assertIn("This is not a firewall", flat)
        self.assertIn("there is no model here", flat)
        self.assertIn("THIRD_PARTY_NOTICES.md", flat)

    def test_the_class_does_not_call_itself_ai(self):
        doc = AIFirewall.__doc__ or ""
        self.assertIn("Not AI", doc)
        self.assertNotIn("AI-driven", doc)

    def test_the_old_class_docstring_is_gone(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn(
            '"""AI-driven firewall (simple packet filter) merged from Deepseek code."""',
            source,
        )

    def test_the_module_does_not_print(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("print(", source)
        self.assertIn('log = logging.getLogger("UmerOS.Security.Firewall")', source)

    def test_the_module_carries_the_section_one_baseline(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertTrue(source.startswith("# This program is free software"))
        self.assertIn("Author:  Umer OS Project", source)
        self.assertIn("License: GPL-3.0 (GNU General Public License v3)", source)
        tree = ast.parse(source)
        self.assertIsInstance(tree.body[0], ast.Expr, "docstring must come first")
        self.assertIsInstance(tree.body[1], ast.ImportFrom)
        self.assertEqual(tree.body[1].module, "__future__")
        self.assertEqual(tree.body[1].names[0].name, "annotations")

    def test_the_provenance_question_is_answered_in_the_notices_file(self):
        notices = (PROJECT_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("No DeepSeek source is vendored", notices)
        self.assertIn("AI-assisted authoring", notices)
        self.assertIn("security/firewall.py", notices)


if __name__ == "__main__":
    unittest.main()
