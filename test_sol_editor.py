import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from pyamf import MixedArray
from pyamf.sol import encode

from sol_app import SOLEditorApp
from sol_editor import SOLFile


class SOLTests(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".sol", dir=".")
        os.close(fd)
        self.path = Path(path)
        self.addCleanup(self.path.unlink, missing_ok=True)

    def fixture(self, data, encoding=0):
        self.path.write_bytes(encode("測試", data, encoding=encoding).getvalue())
        return SOLFile(self.path)

    def test_nested_types_and_encoding_roundtrip(self):
        for encoding in (0, 3):
            with self.subTest(encoding=encoding):
                mixed = MixedArray()
                mixed["entry"] = {"flag": False, "amount": 7, "ratio": 1.5}
                mixed["label"] = "unchanged"
                handler = self.fixture({"items": mixed, "list": ["old"], "nil": None}, encoding)
                handler.update_path(("items", "entry", "flag"), "true")
                handler.update_path(("items", "entry", "amount"), "99")
                handler.update_path(("list", 0), "new\ntext")
                handler.save()
                loaded = SOLFile(self.path)
                self.assertEqual(loaded.encoding, encoding)
                self.assertIsInstance(loaded.data["items"], MixedArray)
                self.assertIs(loaded.get_value(("items", "entry", "flag")), True)
                self.assertEqual(loaded.get_value(("items", "entry", "amount")), 99)
                self.assertEqual(loaded.get_value(("items", "label")), "unchanged")
                self.assertEqual(loaded.get_value(("list", 0)), "new\ntext")
                self.assertIsNone(loaded.data["nil"])

    def test_invalid_edits_leave_values_intact(self):
        handler = self.fixture({"flag": True, "number": 1, "object": {"x": 2}})
        for path, text in ((("flag",), "oops"), (("number",), "1.5"), (("object",), "{}")):
            with self.assertRaises(ValueError):
                handler.update_path(path, text)
        self.assertIs(handler.data["flag"], True)
        self.assertEqual(handler.data["number"], 1)
        self.assertEqual(handler.data["object"], {"x": 2})

    def test_failed_replace_keeps_original_and_cleans_temporary(self):
        handler = self.fixture({"number": 1})
        before = self.path.read_bytes()
        handler.update_value("number", "2")
        temporary = []

        def fail_replace(source, target):
            temporary.append(source)
            raise OSError("simulated failure")

        with patch("sol_editor.os.replace", side_effect=fail_replace):
            with self.assertRaises(OSError):
                handler.save()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(Path(temporary[0]).exists())

    def test_empty_sol_can_save(self):
        handler = self.fixture({})
        handler.save()
        self.assertEqual(SOLFile(self.path).data, {})


class TreeTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = SOLEditorApp(self.root)
        self.addCleanup(self.root.destroy)

    def show(self, data):
        self.app.sol_handler.data = data
        self.app.display_data(data)

    def expand(self, node):
        self.app.tree.focus(node)
        self.app.expand_node()
        self.root.update_idletasks()

    def test_large_container_paginates_without_serializing(self):
        class NoStringDict(dict):
            def __str__(self):
                raise AssertionError("container must not be stringified")

        self.show({"large": NoStringDict((i, i) for i in range(501))})
        node = self.app.tree.get_children()[0]
        self.assertEqual(len(self.app.paths), 1)
        self.expand(node)
        self.assertEqual(len(self.app.tree.get_children(node)), 201)
        self.expand(next(iter(self.app.pages)))
        self.assertEqual(len(self.app.tree.get_children(node)), 401)
        self.expand(next(iter(self.app.pages)))
        self.assertEqual(len(self.app.tree.get_children(node)), 501)
        self.assertEqual(len(self.app.pages), 0)

    def test_cycles_stop_but_shared_objects_expand(self):
        child = {"value": 1}
        data = {"first": child, "second": child}
        data["self"] = data
        self.show(data)
        first, second, cycle = self.app.tree.get_children()
        self.assertFalse(self.app.tree.get_children(cycle))
        self.expand(first)
        self.expand(second)
        self.assertEqual(len(self.app.tree.get_children(first)), 1)
        self.assertEqual(len(self.app.tree.get_children(second)), 1)

    def test_switching_selection_applies_edit_without_changing_other_types(self):
        self.show({"number": 1, "flag": False, "nested": {"x": 2}})
        number, flag, nested = self.app.tree.get_children()
        self.app.tree.selection_set(number)
        self.app.select_node()
        self.app.value_text.delete("1.0", "end")
        self.app.value_text.insert("1.0", "42")
        self.app.tree.selection_set(flag)
        self.app.select_node()
        self.assertEqual(self.app.sol_handler.data["number"], 42)
        self.app.value_text.delete("1.0", "end")
        self.app.value_text.insert("1.0", "true")
        self.assertTrue(self.app.apply_edit())
        self.assertIs(self.app.sol_handler.data["flag"], True)
        self.app.tree.selection_set(nested)
        self.app.select_node()
        self.assertEqual(str(self.app.value_text["state"]), "disabled")
        self.assertIsInstance(self.app.sol_handler.data["nested"], dict)


if __name__ == "__main__":
    unittest.main()
