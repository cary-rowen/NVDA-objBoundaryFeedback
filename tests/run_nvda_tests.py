# Copyright (C) 2026
# This file is covered by the GNU General Public License, version 2 or later.
# pyright: basic
"""Run add-on regressions inside a built, unmodified NVDA source checkout.

Use the checkout's virtualenv Python. No installed NVDA configuration is used.
The NVDA unit bootstrap initializes its own config and native helper libraries.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys
import unittest


def main():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--nvda-root", required=True, type=Path)
	parser.add_argument("--output", required=True, type=Path)
	args = parser.parse_args()
	root = args.nvda_root.resolve()
	output = args.output.resolve()
	testsPath = Path(__file__).resolve().parent / "native" / "test_native_paths.py"
	sys.path[:0] = [str(root), str(root / "source")]
	import tests.unit  # noqa: F401 - official bootstrap (also changes the working directory)
	import xmlrunner

	spec = importlib.util.spec_from_file_location("_boundary_native_tests", testsPath)
	assert spec is not None and spec.loader is not None
	module = importlib.util.module_from_spec(spec)
	sys.modules[spec.name] = module
	spec.loader.exec_module(module)
	output.mkdir(parents=True, exist_ok=True)
	suite = unittest.defaultTestLoader.loadTestsFromModule(module)
	result = xmlrunner.XMLTestRunner(output=str(output), verbosity=2).run(suite)
	return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
	raise SystemExit(main())
