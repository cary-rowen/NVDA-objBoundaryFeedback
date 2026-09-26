# Copyright (C) 2026
# This file is covered by the GNU General Public License, version 2 or later.
# pyright: basic
"""Test the packaged add-on in real Word using NVDA's official Robot spy.

Requires a built NVDA checkout with system-tests dependencies and installed Word.
Use --quick to reuse one isolated document/session per backend. This replaces the
running NVDA temporarily; the caller must restore their regular NVDA afterwards.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import uuid
import zipfile


class ProfileListener:
	ROBOT_LISTENER_API_VERSION = 3

	def __init__(self, bundle, staging, extension):
		self.bundle = bundle
		self.staging = staging
		self.extension = extension
		self.installed = False

	def start_suite(self, data, result):
		if self.installed:
			return
		import NvdaLib
		from robot.libraries.BuiltIn import BuiltIn
		from SystemTestSpy import configManager

		locations = NvdaLib._locations
		locations.stagingDir = str(self.staging)
		locations.profileDir = str(self.staging / "nvdaProfile")
		locations.logPath = str(self.staging / "nvdaProfile/nvda.log")
		original = configManager.setupProfile

		def setup(*args, **kwargs):
			original(*args, **kwargs)
			profile = Path(locations.profileDir)
			with zipfile.ZipFile(self.bundle) as archive:
				destination = profile / "addons/objBoundaryFeedback"
				for name in archive.namelist():
					if not (destination / name).resolve().is_relative_to(destination.resolve()):
						raise ValueError(f"Unsafe bundle entry: {name}")
				archive.extractall(destination)
			backend = BuiltIn().get_variable_value("${WORD_BACKEND}")
			assert backend in ("UIA", "Legacy"), backend
			with (profile / "nvda.ini").open("a", encoding="utf-8") as settings:
				settings.write(f"\n[UIA]\nallowInMSWord = {3 if backend == 'UIA' else 1}\n")
			spy = profile / "scratchpad/globalPlugins/speechSpyGlobalPlugin/__init__.py"
			with spy.open("a", encoding="utf-8") as target:
				target.write("\n" + self.extension.read_text(encoding="utf-8"))

		configManager.setupProfile = setup
		self.installed = True


def main():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--nvda-root", type=Path, required=True)
	parser.add_argument("--output", type=Path, required=True)
	parser.add_argument("--bundle", type=Path, required=True)
	parser.add_argument("--quick", action="store_true", help="Run the short two-backend acceptance flow")
	parser.add_argument(
		"--installed",
		action="store_true",
		help="Use installed NVDA with an isolated profile",
	)
	args = parser.parse_args()
	root = args.nvda_root.resolve()
	output = args.output.resolve()
	bundle = args.bundle.resolve()
	local = Path(__file__).resolve().parent / "system"
	os.environ["UV_PYTHON_PREFERENCE"] = "managed"
	os.chdir(root)
	sys.path[:0] = [str(root / "tests/system/libraries"), str(local)]
	from robot import run

	# Inherit normal output-directory permissions, including across NVDA restarts.
	staging = output / f"profile-{uuid.uuid4().hex}"
	staging.mkdir(parents=True)
	return run(
		str(local / ("quick.robot" if args.quick else "word.robot")),
		outputdir=str(output),
		xunit="systemTests.xml",
		loglevel="DEBUG",
		variable=[f"whichNVDA:{'installed' if args.installed else 'source'}", "installDir:"],
		listener=[ProfileListener(bundle, staging, local / "spy_extension.py")],
	)


if __name__ == "__main__":
	raise SystemExit(main())
