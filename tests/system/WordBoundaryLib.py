# Copyright (C) 2026
# This file is covered by the GNU General Public License, version 2 or later.
# pyright: basic
"""Real Microsoft Word tests using the official NVDA Robot remote spy."""

import time
from pathlib import Path
from typing import Any

from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn
import win32com.client

import NvdaLib
from SystemTestSpy import _getLib


class WordBoundaryLib:
	ROBOT_LIBRARY_SCOPE = "SUITE"

	def __init__(self):
		self.word: Any = None
		self.document: Any = None
		self.spy: Any = None  # Robot remote library extended by spy_extension.py.

	def start_word_test(self, backend):
		self.backend = backend
		BuiltIn().set_suite_variable("${WORD_BACKEND}", backend)
		_getLib("NvdaLib").start_NVDA("standard-dontShowWelcomeDialog.ini")
		self.spy = NvdaLib.getSpyLib()
		self.word = win32com.client.DispatchEx("Word.Application")
		assert self.word.Documents.Count == 0, "Word did not create an isolated automation instance"
		self.word.Visible = True
		self.document = self.word.Documents.Add()
		fixtures = Path(BuiltIn().get_variable_value("${OUTPUT DIR}")) / "word-fixtures"
		fixtures.mkdir(parents=True, exist_ok=True)
		self.document.SaveAs2(str(fixtures / f"BoundaryRobot{time.time_ns()}.docx"), 16)
		self.document.Activate()
		self.word.Activate()
		self.document.Content.Select()
		self.word.Selection.Collapse(1)
		self.spy.emulateKeyPress("alt")
		self.spy.emulateKeyPress("escape")
		self.spy.boundary_probe(focus_window=int(self.document.ActiveWindow.Hwnd))
		self.document.ActiveWindow.Activate()
		self.document.Range(0, 0).Select()
		self.spy.emulateKeyPress("alt+tab")
		self.spy.emulateKeyPress("alt+tab")
		self._wait_for_word()
		state = self.spy.boundary_probe(True)
		if not state["focusMode"]:
			self.spy.emulateKeyPress("insert+space")
			state = self.spy.boundary_probe(True)
		assert state["focusMode"], state
		logger.info(f"Word {self.word.Version}, build {self.word.Build}; backend evidence: {state}")

	def stop_word_test(self):
		try:
			if BuiltIn().get_variable_value("${TEST STATUS}") == "FAIL":
				name = BuiltIn().get_variable_value("${TEST NAME}")
				path = Path(BuiltIn().get_variable_value("${OUTPUT DIR}")) / f"{name}.png"
				_getLib("ScreenCapLibrary").take_screenshot(str(path))
		finally:
			try:
				if self.document is not None:
					self.document.Close(0)
				if self.word is not None and self.word.Documents.Count == 0:
					self.word.Quit(0)
			finally:
				self.document = None
				self.word = None
				_getLib("NvdaLib").quit_NVDA()

	def _wait_for_word(self):
		deadline = time.monotonic() + 15
		while time.monotonic() < deadline:
			state = self.spy.boundary_probe()
			if (
				state["backend"] == self.backend
				and state["foreground"] == int(self.document.ActiveWindow.Hwnd)
				and state["focusRoot"] == int(self.document.ActiveWindow.Hwnd)
			):
				return state
			time.sleep(0.1)
		raise AssertionError(f"Expected real {self.backend} Word provider, got {state}")

	def _fixture(self, text):
		self.document.Content.Text = text
		self.document.Range(0, 0).Select()
		self._wait_for_word()
		self.spy.wait_for_speech_to_finish()

	def _key(self, key, expected, mode=3):
		self.spy.boundary_probe(True, mode)
		before = (self.word.Selection.Start, self.word.Selection.End)
		self._send(key)
		state = self.spy.boundary_probe(False, mode)
		after = (self.word.Selection.Start, self.word.Selection.End)
		logger.info(f"{self.backend}: {key}, selection {before} -> {after}, {state}")
		assert state["backend"] == self.backend, state
		assert state["focusMode"], state
		assert state["waves"] == expected, (key, before, after, state)
		return before, after

	def _send(self, key):
		state = self.spy.boundary_probe()
		assert state["foreground"] == int(self.document.ActiveWindow.Hwnd), state
		assert state["focusRoot"] == int(self.document.ActiveWindow.Hwnd), state
		self.spy.emulateKeyPress(key)

	def verify_word_boundaries(self, fixture):
		texts = {
			"empty": "",
			"single": "A single line.",
			"paragraphs": "First paragraph.\rMiddle paragraph.\rLast paragraph.",
			"wrapped": "A long paragraph wraps naturally. " * 35,
			"blank-final": "First paragraph.\rSecond paragraph.\r",
			"manual-breaks": "First line.\vSecond line.\vLast line.",
		}
		self._fixture(texts[fixture])
		for position, keys, wave in (
			("control+home", ("upArrow", "control+upArrow"), "boundaryPrevious.wav"),
			("control+end", ("downArrow", "control+downArrow"), "boundaryNext.wav"),
		):
			for key in keys:
				self._send(position)
				for _ in range(3):
					before, after = self._key(key, [wave])
					assert before == after, (key, before, after)

	def verify_successful_moves_and_selection(self):
		self._fixture("First paragraph.\rMiddle paragraph.\rLast paragraph.")
		for start, key in (
			("control+home", "downArrow"),
			("control+home", "control+downArrow"),
			("control+end", "upArrow"),
			("control+end", "control+upArrow"),
		):
			self._send(start)
			before, after = self._key(key, [])
			assert before != after, (key, before, after)
		for key in ("upArrow", "downArrow", "control+upArrow", "control+downArrow"):
			self.document.Content.Select()
			self.spy.wait_for_speech_to_finish()
			assert not self.spy.boundary_probe()["collapsed"]
			self._key(key, [])
			assert self.spy.boundary_probe()["collapsed"]

	def verify_disabled_feedback(self):
		self._fixture("Only one line.")
		for start, key in (
			("control+home", "upArrow"),
			("control+home", "control+upArrow"),
			("control+end", "downArrow"),
			("control+end", "control+downArrow"),
		):
			self._send(start)
			self._key(key, [], mode=0)
