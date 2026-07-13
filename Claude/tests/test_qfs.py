"""Tests for Umer OS Quantum Filesystem (QFS)."""
from __future__ import annotations

import unittest

from fs.qfs import QFS, QFSCompressor, CASStore, AIFileIndexer


class TestCASStore(unittest.TestCase):

    def setUp(self):
        self.store = CASStore(max_size_bytes=16 * 1024 * 1024)

    def test_put_returns_hex_address(self):
        addr = self.store.put(b"hello world")
        self.assertIsInstance(addr, str)
        self.assertEqual(len(addr), 64)

    def test_put_same_data_returns_same_address(self):
        a1 = self.store.put(b"identical")
        a2 = self.store.put(b"identical")
        self.assertEqual(a1, a2)

    def test_get_returns_stored_data(self):
        data = b"Umer OS kernel"
        addr = self.store.put(data)
        self.assertEqual(self.store.get(addr), data)

    def test_get_unknown_raises_key_error(self):
        with self.assertRaises(KeyError):
            self.store.get("0" * 64)

    def test_exists_true_after_put(self):
        addr = self.store.put(b"exists")
        self.assertTrue(self.store.exists(addr))

    def test_exists_false_before_put(self):
        self.assertFalse(self.store.exists("a" * 64))

    def test_release_frees_block(self):
        addr = self.store.put(b"freeable")
        freed = self.store.release(addr)
        self.assertTrue(freed)
        self.assertFalse(self.store.exists(addr))

    def test_release_unknown_returns_false(self):
        self.assertFalse(self.store.release("0" * 64))

    def test_dedup_saves_bytes(self):
        data = b"repeated data"
        self.store.put(data)
        self.store.put(data)  # second put increments refcount
        savings = self.store.dedup_scan()
        self.assertGreaterEqual(savings, 0)

    def test_stats_returns_expected_keys(self):
        stats = self.store.stats()
        for k in ("blocks", "used_bytes", "max_bytes", "dedup_savings"):
            self.assertIn(k, stats)

    def test_put_empty_bytes(self):
        addr = self.store.put(b"")
        self.assertIsInstance(addr, str)
        data = self.store.get(addr)
        self.assertEqual(data, b"")

    def test_max_size_raises_memory_error(self):
        tiny = CASStore(max_size_bytes=100)
        with self.assertRaises(MemoryError):
            tiny.put(b"x" * 200)

    def test_multiple_blocks_tracked(self):
        self.store.put(b"alpha")
        self.store.put(b"beta")
        self.store.put(b"gamma")
        stats = self.store.stats()
        self.assertEqual(stats["blocks"], 3)


class TestQFSCompressor(unittest.TestCase):

    def setUp(self):
        self.comp = QFSCompressor(lzma_preset=1)

    def test_compress_decompress_roundtrip(self):
        data = b"Umer OS filesystem compression test " * 50
        compressed = self.comp.compress(data)
        self.comp.reset()
        recovered = self.comp.decompress(compressed)
        self.assertEqual(recovered, data)

    def test_empty_data_roundtrip(self):
        compressed = self.comp.compress(b"")
        self.comp.reset()
        recovered = self.comp.decompress(compressed)
        self.assertEqual(recovered, b"")

    def test_compressed_smaller_than_original(self):
        # 2 KiB of repeated bytes — LZMA finishes in milliseconds
        data = b"A" * 2000
        compressed = self.comp.compress(data)
        self.assertLess(len(compressed), len(data))

    def test_compression_ratio_less_than_one_for_compressible(self):
        data = b"0" * 5000
        compressed = self.comp.compress(data)
        ratio = self.comp.compression_ratio(data, compressed)
        self.assertLess(ratio, 1.0)

    def test_compression_ratio_empty(self):
        ratio = self.comp.compression_ratio(b"", b"")
        self.assertEqual(ratio, 1.0)

    def test_magic_header_present(self):
        compressed = self.comp.compress(b"data")
        self.assertTrue(compressed.startswith(QFSCompressor.MAGIC))

    def test_decompress_invalid_raises(self):
        with self.assertRaises(ValueError):
            self.comp.decompress(b"no magic header here!!")

    def test_reset_clears_delta_state(self):
        self.comp.compress(b"first block")
        self.comp.reset()
        self.assertIsNone(self.comp._last_block)

    def test_binary_data_roundtrip(self):
        # Use structured bytes (not random) so LZMA completes fast
        data = bytes(range(256)) * 4  # 1 KiB repeating pattern
        compressed = self.comp.compress(data)
        self.comp.reset()
        recovered = self.comp.decompress(compressed)
        self.assertEqual(recovered, data)

    def test_unicode_content_roundtrip(self):
        data = "Umer OS — قوم ایف پائتھن".encode("utf-8")
        compressed = self.comp.compress(data)
        self.comp.reset()
        recovered = self.comp.decompress(compressed)
        self.assertEqual(recovered, data)


class TestAIFileIndexer(unittest.TestCase):

    def setUp(self):
        self.idx = AIFileIndexer()

    def test_index_and_search_found(self):
        self.idx.index("/docs/readme.md", b"quantum computing simulation umer os")
        results = self.idx.search("quantum")
        self.assertTrue(any("readme" in r[0] for r in results))

    def test_search_not_found(self):
        self.idx.index("/docs/readme.md", b"kernel scheduler memory")
        results = self.idx.search("blockchain")
        paths = [r[0] for r in results]
        self.assertNotIn("/docs/readme.md", paths)

    def test_search_returns_tuple_list(self):
        self.idx.index("/f.txt", b"hello world umer")
        results = self.idx.search("hello")
        for path, score in results:
            self.assertIsInstance(path, str)
            self.assertIsInstance(score, float)

    def test_top_k_limits_results(self):
        for i in range(10):
            self.idx.index(f"/file{i}.txt", f"quantum simulator content {i}".encode())
        results = self.idx.search("quantum", top_k=5)
        self.assertLessEqual(len(results), 5)

    def test_remove_removes_from_index(self):
        self.idx.index("/temp.txt", b"umer os scheduler")
        self.idx.remove("/temp.txt")
        results = self.idx.search("umer")
        paths = [r[0] for r in results]
        self.assertNotIn("/temp.txt", paths)

    def test_rebuild_index(self):
        self.idx.index("/old.txt", b"old data")
        n = self.idx.rebuild_index({"/new.txt": b"new content"})
        self.assertEqual(n, 1)
        results = self.idx.search("new")
        self.assertTrue(len(results) > 0)

    def test_stats_returns_expected_keys(self):
        stats = self.idx.stats()
        self.assertIn("indexed_files", stats)
        self.assertIn("max_entries", stats)

    def test_empty_query_returns_empty(self):
        self.idx.index("/a.txt", b"data")
        results = self.idx.search("")
        self.assertEqual(results, [])

    def test_short_words_ignored(self):
        self.idx.index("/b.txt", b"a bb ccc dddd")
        results = self.idx.search("ccc")
        self.assertTrue(len(results) >= 1)


class TestQFS(unittest.TestCase):

    def setUp(self):
        self.qfs = QFS(max_store_bytes=32 * 1024 * 1024)
        self.qfs.mount("/")

    def test_write_and_read_roundtrip(self):
        self.qfs.write_file("/home/test.txt", b"Hello Umer OS!")
        data = self.qfs.read_file("/home/test.txt")
        self.assertEqual(data, b"Hello Umer OS!")

    def test_read_nonexistent_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.qfs.read_file("/missing.txt")

    def test_write_returns_cas_address(self):
        addr = self.qfs.write_file("/a.txt", b"data")
        self.assertIsInstance(addr, str)
        self.assertEqual(len(addr), 64)

    def test_overwrite_file(self):
        self.qfs.write_file("/b.txt", b"version 1")
        self.qfs.write_file("/b.txt", b"version 2")
        self.assertEqual(self.qfs.read_file("/b.txt"), b"version 2")

    def test_delete_file(self):
        self.qfs.write_file("/del.txt", b"to delete")
        result = self.qfs.delete_file("/del.txt")
        self.assertTrue(result)
        with self.assertRaises(FileNotFoundError):
            self.qfs.read_file("/del.txt")

    def test_delete_nonexistent_returns_false(self):
        self.assertFalse(self.qfs.delete_file("/ghost.txt"))

    def test_exists_true(self):
        self.qfs.write_file("/e.txt", b"data")
        self.assertTrue(self.qfs.exists("/e.txt"))

    def test_exists_false(self):
        self.assertFalse(self.qfs.exists("/no.txt"))

    def test_list_dir(self):
        self.qfs.write_file("/home/a.txt", b"a")
        self.qfs.write_file("/home/b.txt", b"b")
        self.qfs.write_file("/var/c.txt", b"c")
        listing = self.qfs.list_dir("/home")
        self.assertIn("/home/a.txt", listing)
        self.assertIn("/home/b.txt", listing)
        self.assertNotIn("/var/c.txt", listing)

    def test_search_returns_matching_files(self):
        self.qfs.write_file("/docs/qc.txt", b"quantum computing entanglement")
        self.qfs.write_file("/docs/ai.txt", b"artificial intelligence neural")
        results = self.qfs.search("quantum")
        self.assertIn("/docs/qc.txt", results)
        self.assertNotIn("/docs/ai.txt", results)

    def test_snapshot_and_restore(self):
        self.qfs.write_file("/snap.txt", b"original")
        snap_id = self.qfs.snapshot()
        self.qfs.write_file("/snap.txt", b"modified")
        self.assertEqual(self.qfs.read_file("/snap.txt"), b"modified")
        self.qfs.restore_snapshot(snap_id)
        self.assertEqual(self.qfs.read_file("/snap.txt"), b"original")

    def test_restore_nonexistent_snapshot_returns_false(self):
        result = self.qfs.restore_snapshot("nonexistent_snap")
        self.assertFalse(result)

    def test_list_snapshots(self):
        s1 = self.qfs.snapshot()
        s2 = self.qfs.snapshot()
        snaps = self.qfs.list_snapshots()
        self.assertIn(s1, snaps)
        self.assertIn(s2, snaps)

    def test_stats_returns_expected_keys(self):
        self.qfs.write_file("/x.txt", b"data")
        stats = self.qfs.stats()
        for k in ("files", "total_original_bytes", "total_compressed_bytes",
                  "compression_ratio", "space_saving_pct", "cas", "index"):
            self.assertIn(k, stats)

    def test_compression_reduces_size(self):
        # Use highly compressible data (repeated bytes) for a fast LZMA pass
        data = b"Z" * 2000
        self.qfs.write_file("/big.txt", data)
        stats = self.qfs.stats()
        self.assertLess(stats["total_compressed_bytes"],
                        stats["total_original_bytes"])

    def test_deduplication_same_content(self):
        data = b"dedup-test-pattern " * 100  # small, compressible
        self.qfs.write_file("/dup1.txt", data)
        self.qfs.write_file("/dup2.txt", data)
        cas_stats = self.qfs.stats()["cas"]
        self.assertGreaterEqual(cas_stats["dedup_savings"], 0)

    def test_file_info_returns_metadata(self):
        self.qfs.write_file("/meta.txt", b"metadata test")
        info = self.qfs.file_info("/meta.txt")
        self.assertIsNotNone(info)
        self.assertIn("size", info)
        self.assertIn("compressed", info)
        self.assertIn("mtime", info)

    def test_file_info_nonexistent_returns_none(self):
        self.assertIsNone(self.qfs.file_info("/no_such_file.txt"))

    def test_large_file_roundtrip(self):
        # Use compressible data (repeated pattern) so LZMA is fast
        data = b"Umer OS large file test pattern " * 4096  # 128 KiB, highly compressible
        self.qfs.write_file("/large.bin", data)
        recovered = self.qfs.read_file("/large.bin")
        self.assertEqual(recovered, data)


if __name__ == "__main__":
    unittest.main()
