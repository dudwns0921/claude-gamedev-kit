#!/usr/bin/env python3
"""Structure checks — the rules in CLAUDE.md that can be told from the files alone. Runs nothing.

  python3 tests/test_structure.py

Do the files the skill documents and hooks point to exist, are the scripts free of branches on an engine's name, do they use the standard library only.
"""
import ast
import glob
import os
import re
import sys
import unittest

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOT_STDLIB = {"blender_finish.py": {"bpy"}}  # the script Blender runs


def rel(path):
    return os.path.relpath(path, KIT)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def scripts():
    return sorted(glob.glob(os.path.join(KIT, "skills", "*", "scripts", "*.py"))
                  + glob.glob(os.path.join(KIT, "hooks", "*.py")) + glob.glob(os.path.join(KIT, "tools", "*.py")))


def imports(path):
    for node in ast.walk(ast.parse(read(path))):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and not node.level:
            yield node.module.split(".")[0]


class Structure(unittest.TestCase):
    def test_paths_exist(self):
        """The scripts · documents the skill documents call, and the scripts the hooks call, exist."""
        seen = 0
        for path in sorted(glob.glob(os.path.join(KIT, "skills", "**", "*.md"), recursive=True)):
            skill = os.path.join(KIT, "skills", rel(path).split(os.sep)[1])
            for target in re.findall(r"\$\{CLAUDE_SKILL_DIR\}/([\w./-]*\w)", read(path)):
                seen += 1
                with self.subTest(rel(path), target=target):
                    self.assertTrue(os.path.exists(os.path.join(skill, target)))
        for target in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]*\w)", read(os.path.join(KIT, "hooks", "hooks.json"))):
            seen += 1
            with self.subTest("hooks/hooks.json", target=target):
                self.assertTrue(os.path.exists(os.path.join(KIT, target)))
        self.assertTrue(seen, "found no path pointed to at all — has the way they are written changed?")

    def test_no_engine_branches(self):
        """Engine names live in engines/ only — scripts look at the values in kit.config.json alone."""
        engines = [os.path.basename(p) for p in glob.glob(os.path.join(KIT, "engines", "*")) if os.path.isdir(p)]
        self.assertTrue(engines)
        for path in scripts():
            with self.subTest(rel(path)):
                found = [n.value for n in ast.walk(ast.parse(read(path)))
                         if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.lower() in engines]
                self.assertEqual(found, [])

    def test_stdlib_only(self):
        """Imports only the standard library and what is in the same folder."""
        if not hasattr(sys, "stdlib_module_names"):
            self.skipTest("can only be checked from Python 3.10 on")
        for path in scripts():
            with self.subTest(rel(path)):
                here = {os.path.basename(p)[:-3] for p in glob.glob(os.path.join(os.path.dirname(path), "*.py"))}
                allowed = set(sys.stdlib_module_names) | here | NOT_STDLIB.get(os.path.basename(path), set())
                self.assertEqual(sorted(set(imports(path)) - allowed), [])


if __name__ == "__main__":
    unittest.main()
