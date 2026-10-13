#!/usr/bin/env python3
"""구조 검사 — CLAUDE.md 의 규칙 가운데 파일만 봐도 알 수 있는 것을 본다. 아무것도 돌리지 않는다.

  python3 tests/test_structure.py

스킬 문서와 훅이 가리키는 파일이 있는가, 스크립트에 엔진 이름으로 갈리는 분기가 없는가, 표준 라이브러리만 쓰는가.
"""
import ast
import glob
import os
import re
import sys
import unittest

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOT_STDLIB = {"blender_finish.py": {"bpy"}}  # Blender 가 돌리는 스크립트


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
        """스킬 문서가 부르는 스크립트 · 문서, 훅이 부르는 스크립트가 있다."""
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
        self.assertTrue(seen, "가리키는 경로를 하나도 찾지 못했다 — 적는 꼴이 바뀌었는가")

    def test_no_engine_branches(self):
        """엔진 이름은 engines/ 에만 있다 — 스크립트는 kit.config.json 의 값만 본다."""
        engines = [os.path.basename(p) for p in glob.glob(os.path.join(KIT, "engines", "*")) if os.path.isdir(p)]
        self.assertTrue(engines)
        for path in scripts():
            with self.subTest(rel(path)):
                found = [n.value for n in ast.walk(ast.parse(read(path)))
                         if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.lower() in engines]
                self.assertEqual(found, [])

    def test_stdlib_only(self):
        """표준 라이브러리와 같은 폴더의 것만 import 한다."""
        if not hasattr(sys, "stdlib_module_names"):
            self.skipTest("Python 3.10 부터 볼 수 있다")
        for path in scripts():
            with self.subTest(rel(path)):
                here = {os.path.basename(p)[:-3] for p in glob.glob(os.path.join(os.path.dirname(path), "*.py"))}
                allowed = set(sys.stdlib_module_names) | here | NOT_STDLIB.get(os.path.basename(path), set())
                self.assertEqual(sorted(set(imports(path)) - allowed), [])


if __name__ == "__main__":
    unittest.main()
