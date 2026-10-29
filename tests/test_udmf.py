"""Tests for UmerOS UDMF and Uniform Type Descriptors."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.udmf.utd_registry import UTDRegistry, UniformTypeDescriptor, UTD_HIERARCHY
from core.udmf.unified_data import UnifiedData, DataRepresentation


class TestUniformTypeDescriptor(unittest.TestCase):
    def test_ancestors(self):
        utd = UniformTypeDescriptor("general.plain-text")
        ancestors = utd.ancestors()
        self.assertEqual(ancestors[0], "general.plain-text")
        self.assertIn("general.text", ancestors)
        self.assertIn("general.entity", ancestors)

    def test_conforms_to(self):
        utd = UniformTypeDescriptor("general.plain-text")
        self.assertTrue(utd.conforms_to("general.text"))
        self.assertTrue(utd.conforms_to("general.entity"))
        self.assertTrue(utd.conforms_to("general.plain-text"))
        self.assertFalse(utd.conforms_to("general.image"))

    def test_umeros_types(self):
        utd = UniformTypeDescriptor("umeros.quantum-qasm")
        self.assertTrue(utd.conforms_to("general.text"))
        self.assertTrue(utd.conforms_to("general.entity"))

    def test_children_of(self):
        reg = UTDRegistry()
        children = reg.children_of("general.text")
        self.assertIn("general.plain-text", children)
        self.assertIn("general.html", children)

    def test_all_subtypes(self):
        reg = UTDRegistry()
        subtypes = reg.all_subtypes("general.text")
        self.assertIn("general.plain-text", subtypes)
        self.assertIn("general.html", subtypes)
        self.assertIn("general.markdown", subtypes)

    def test_register_custom_type(self):
        reg = UTDRegistry()
        utd = reg.register("custom.my-type", parent="general.entity")
        self.assertTrue(reg.exists("custom.my-type"))
        self.assertTrue(reg.conforms("custom.my-type", "general.entity"))


class TestUTDRegistry(unittest.TestCase):
    def test_mime_to_utd(self):
        reg = UTDRegistry()
        self.assertEqual(reg.mime_to_utd("text/plain"), "general.plain-text")
        self.assertEqual(reg.mime_to_utd("image/png"), "general.image")
        self.assertIsNone(reg.mime_to_utd("application/unknown"))

    def test_ext_to_utd(self):
        reg = UTDRegistry()
        self.assertEqual(reg.ext_to_utd(".txt"), "general.plain-text")
        self.assertEqual(reg.ext_to_utd(".qasm"), "umeros.quantum-qasm")
        self.assertEqual(reg.ext_to_utd("png"), "general.image")

    def test_conforms_method(self):
        reg = UTDRegistry()
        self.assertTrue(reg.conforms("general.plain-text", "general.entity"))
        self.assertFalse(reg.conforms("general.plain-text", "general.image"))

    def test_list_types(self):
        reg = UTDRegistry()
        types = reg.list_types()
        self.assertIn("general.plain-text", types)
        self.assertIn("umeros.quantum-qasm", types)


class TestUnifiedData(unittest.TestCase):
    def test_add_and_get_representation(self):
        ud = UnifiedData(source_app="test_app")
        ud.add_representation(DataRepresentation(utd_type="general.plain-text", data="Hello"))
        rep = ud.get_representation("general.plain-text")
        self.assertIsNotNone(rep)
        self.assertEqual(rep.data, "Hello")

    def test_conformance_get(self):
        ud = UnifiedData()
        ud.add_representation(DataRepresentation(utd_type="general.plain-text", data="Hello"))
        # Should find via conformance (plain-text conforms to text)
        rep = ud.get_representation("general.text")
        self.assertIsNotNone(rep)

    def test_has_type(self):
        ud = UnifiedData()
        ud.add_representation(DataRepresentation(utd_type="general.image", data=b"\x89PNG"))
        self.assertTrue(ud.has_type("general.image"))
        self.assertTrue(ud.has_type("general.media"))
        self.assertFalse(ud.has_type("general.text"))

    def test_primary_type(self):
        ud = UnifiedData()
        ud.add_representation(DataRepresentation(utd_type="general.plain-text", data="Hello"))
        ud.add_representation(DataRepresentation(utd_type="general.html", data="<p>Hello</p>"))
        self.assertEqual(ud.primary_type(), "general.plain-text")

    def test_total_size(self):
        ud = UnifiedData()
        ud.add_representation(DataRepresentation(utd_type="general.plain-text", data="Hello"))
        self.assertGreater(ud.total_size(), 0)

    def test_content_hash(self):
        ud = UnifiedData()
        ud.add_representation(DataRepresentation(utd_type="general.plain-text", data="Hello"))
        h1 = ud.content_hash()
        ud2 = UnifiedData()
        ud2.add_representation(DataRepresentation(utd_type="general.plain-text", data="Hello"))
        self.assertEqual(h1, ud2.content_hash())

    def test_serialization_roundtrip(self):
        ud = UnifiedData(source_app="test", source_node="node1")
        ud.add_representation(DataRepresentation(utd_type="general.plain-text", data="Hello"))
        d = ud.to_dict()
        restored = UnifiedData.from_dict(d)
        self.assertEqual(restored.source_app, "test")
        self.assertEqual(restored.representations[0].data, "Hello")

    def test_repr(self):
        ud = UnifiedData()
        ud.add_representation(DataRepresentation(utd_type="general.plain-text", data="Hi"))
        r = repr(ud)
        self.assertIn("general.plain-text", r)


if __name__ == "__main__":
    unittest.main()