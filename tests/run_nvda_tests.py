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
from unittest.mock import Mock


def main():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--nvda-root", required=True, type=Path)
	parser.add_argument("--output", required=True, type=Path)
	parser.add_argument(
		"--upstream",
		action="store_true",
		help="Run NVDA's unit suite with the add-on loaded",
	)
	parser.add_argument(
		"--plugin-source",
		type=Path,
		help="Alternate plugin __init__.py for a negative control",
	)
	parser.add_argument("--test-pattern", action="append", help="Select native test methods by glob pattern")
	args = parser.parse_args()
	root = args.nvda_root.resolve()
	output = args.output.resolve()
	pluginSource = args.plugin_source.resolve() if args.plugin_source else None
	testsPath = Path(__file__).resolve().parent / "native" / "test_native_paths.py"
	sys.path[:0] = [str(root), str(root / "source")]
	import tests.unit  # noqa: F401 - official bootstrap (also changes the working directory)
	import xmlrunner

	spec = importlib.util.spec_from_file_location("_boundary_native_tests", testsPath)
	assert spec is not None and spec.loader is not None
	module = importlib.util.module_from_spec(spec)
	sys.modules[spec.name] = module
	spec.loader.exec_module(module)
	if pluginSource is not None:
		setattr(module, "PLUGIN_PATH", pluginSource)
	if args.test_pattern:
		unittest.defaultTestLoader.testNamePatterns = args.test_pattern
	output.mkdir(parents=True, exist_ok=True)
	if args.upstream:
		plugin = module.loadPlugin().GlobalPlugin()
		plugin._playBoundarySound = Mock()  # retain enabled modes without audible output
		try:
			suite = unittest.defaultTestLoader.discover(str(root / "tests/unit"), top_level_dir=str(root))
			result = xmlrunner.XMLTestRunner(output=str(output), verbosity=1).run(suite)
		finally:
			plugin.terminate()
	else:
		suite = unittest.defaultTestLoader.loadTestsFromModule(module)
		result = xmlrunner.XMLTestRunner(output=str(output), verbosity=2).run(suite)
	return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
	raise SystemExit(main())
