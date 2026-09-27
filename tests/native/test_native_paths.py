# Copyright (C) 2026
# This file is covered by the GNU General Public License, version 2 or later.
# pyright: basic
"""NVDA Word routing and TextInfo regressions with controlled application I/O."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path
import sys
from typing import Any, cast
import unittest
from unittest.mock import Mock, patch

import addonHandler
import api
from baseObject import ScriptableObject
import braille
import config
import controlTypes
from documentNavigation import paragraphHelper
import editableText
import eventHandler
import IAccessibleHandler
from keyboardHandler import KeyboardInputGesture
from NVDAObjects.IAccessible.winword import WordDocument as LegacyWord
from NVDAObjects.UIA.wordDocument import WordDocument as UIAWord
import review
import scriptHandler
import speech
import textInfos
from tests.unit.textProvider import BasicTextInfo, BasicTextProvider, CursorManager


PLUGIN_PACKAGE = Path(__file__).resolve().parents[2] / "addon/globalPlugins/objBoundaryFeedback"
PLUGIN_PATH = PLUGIN_PACKAGE / "__init__.py"


def loadPlugin():
	name = "_boundary_addon_native"
	if name in sys.modules:
		return sys.modules[name]
	spec = importlib.util.spec_from_file_location(
		name,
		PLUGIN_PATH,
		submodule_search_locations=[str(PLUGIN_PACKAGE)],
	)
	assert spec is not None and spec.loader is not None
	module = importlib.util.module_from_spec(spec)
	sys.modules[name] = module
	# This source tree is not installed as an add-on; use NVDA's English gettext
	# already initialized by tests.unit. All other NVDA modules stay real.
	with patch.object(addonHandler, "initTranslation"):
		spec.loader.exec_module(module)
	return module


class WordRange(BasicTextInfo):
	"""Provider seam for native Legacy scripts' Range.move/updateCaret contract."""

	@property
	def _rangeObj(self):
		return self

	def move(self, unit, direction, endPoint=None):
		provider = cast(WordProvider, self.obj)
		if isinstance(unit, int):  # wdParagraph, used directly by Legacy Word
			provider.comMoves.append((unit, direction))
			if provider.destination is not None:
				self._startOffset = self._endOffset = provider.destination
			if provider.comAction is not None:
				provider.comAction()
			return 0  # The plug-in must compare actual endpoints, not this count.
		if unit in (textInfos.UNIT_LINE, textInfos.UNIT_PARAGRAPH):
			provider.probes.append((unit, direction))
			# Simulate the provider being able to move past a keyboard boundary.
			return direction
		return super().move(unit, direction, endPoint)


class WordProvider(BasicTextProvider):
	TextInfo = WordRange

	def __init__(self, text="one\ntwo\n", selection=(0, 0)):
		super().__init__(text=text, selection=selection)
		self.comMoves = []
		self.probes = []
		self.destination: int | None = None
		self.comAction: Callable[[], None] | None = None

	def makeTextInfo(self, position):
		info = super().makeTextInfo(position)
		if position == textInfos.POSITION_CARET:
			info.collapse()  # Word's caret hides a non-collapsed selection.
		return info


class EditableProvider(editableText.EditableText, BasicTextProvider):
	caretMovementDetectionUsesEvents = False
	_caretMovementTimeoutMultiplier = 0


def wordObject(cls, provider):
	# Use the actual class and native scripts, avoiding a live HWND/COM server
	# for deterministic testing. Only application-facing data is substituted.
	obj = object.__new__(cls)
	obj._propertyCache = {}
	obj.makeTextInfo = provider.makeTextInfo
	obj.value = "document text"
	obj.windowText = "test document"
	obj.parent = None
	obj.shouldFireCaretMovementFailedEvents = False
	obj.caretMovementDetectionUsesEvents = False
	obj._caretMovementTimeoutMultiplier = 0  # one native poll, no wall-clock wait
	ScriptableObject.__init__(obj)
	return obj


class NativePathTests(unittest.TestCase):
	def setUp(self):
		self.module = loadPlugin()
		self.plugin = self.module.GlobalPlugin()
		self.addCleanup(self.plugin.terminate)
		self.plugin._playBoundarySound = Mock()
		self.conf = self.module.addonConfig
		self.section = cast(config.AggregatedSection, config.conf[self.conf.CONF_SECTION])
		self.oldConfig = {setting.key: self.section[setting.key] for setting in self.conf.SCENARIO_SETTINGS}
		self.addCleanup(self.restoreConfig)
		self.section[self.conf.SCENARIO_EDITABLE_TEXT_CARET] = 3
		self.section[self.conf.SCENARIO_BROWSE_MODE_VIRTUAL_CURSOR] = 3
		self.focus = self.startPatch(api, "getFocusObject")
		self.startPatch(api, "processPendingEvents")
		self.pending = self.startPatch(eventHandler, "isPendingEvents", return_value=False)
		self.startPatch(editableText, "willSayAllResume", return_value=False)
		self.speak = self.startPatch(speech, "speakTextInfo")
		self.reviewMove = self.startPatch(review, "handleCaretMove")
		self.brailleMove = self.startPatch(braille.handler, "handleCaretMove")

	def restoreConfig(self):
		for key, value in self.oldConfig.items():
			self.section[key] = value

	def startPatch(self, owner, name, **kwargs):
		patcher = patch.object(owner, name, **kwargs)
		result = patcher.start()
		self.addCleanup(patcher.stop)
		return result

	def runKey(self, cls, key, selection=(0, 0), destination=None, text="one\ntwo\n"):
		provider = WordProvider(text=text, selection=selection)
		provider.destination = destination
		obj = wordObject(cls, provider)
		self.focus.return_value = obj
		gesture = KeyboardInputGesture.fromName(key)
		gesture.send = Mock(
			side_effect=lambda: (
				setattr(provider, "selectionOffsets", (destination, destination))
				if destination is not None
				else None
			),
		)
		script = scriptHandler._getObjScript(obj, gesture, [])
		assert script is not None
		script(gesture)
		self.assertEqual(provider.probes, [], "Word feedback must not probe virtual line/paragraph movement")
		self.assertNotIn("_hasCaretMoved", obj.__dict__)
		return obj, provider, gesture

	def test_both_backends_vertical_keys_at_both_boundaries(self):
		for cls in (UIAWord, LegacyWord):
			for text, position in (("", 0), ("one", 0), ("one\ntwo\n", 7)):
				for key in ("upArrow", "downArrow", "control+upArrow", "control+downArrow"):
					with self.subTest(backend=cls.__module__, text=text, key=key):
						self.plugin._playBoundarySound.reset_mock()
						self.speak.reset_mock()
						_, provider, gesture = self.runKey(cls, key, (position, position), text=text)
						direction = "previous" if "upArrow" in key else "next"
						self.plugin._playBoundarySound.assert_called_once_with(direction)
						self.speak.assert_called_once()
						if cls is LegacyWord and key.startswith("control"):
							cast(Mock, gesture.send).assert_not_called()
							self.assertEqual(provider.comMoves, [(4, -1 if direction == "previous" else 1)])
						else:
							cast(Mock, gesture.send).assert_called_once_with()
							self.assertEqual(provider.comMoves, [])

	def test_successful_movement_and_arrival_at_edge_are_silent(self):
		for cls in (UIAWord, LegacyWord):
			for key, dest in (
				("upArrow", 0),
				("downArrow", 7),
				("control+upArrow", 0),
				("control+downArrow", 7),
			):
				with self.subTest(backend=cls.__module__, key=key):
					self.runKey(cls, key, (3, 3), dest)
					self.plugin._playBoundarySound.assert_not_called()

	def test_selection_collapse_is_not_a_boundary(self):
		for cls in (UIAWord, LegacyWord):
			for key in ("upArrow", "downArrow", "control+upArrow", "control+downArrow"):
				with self.subTest(backend=cls.__module__, key=key):
					self.runKey(cls, key, (0, 3), 0)
					self.plugin._playBoundarySound.assert_not_called()

	def test_legacy_rebound_non_keyboard_script_keeps_semantic_direction_and_metadata(self):
		provider = WordProvider()
		obj = wordObject(LegacyWord, provider)
		obj.bindGesture("br(test):advance", "nextParagraph")
		gesture = Mock(normalizedIdentifiers=["br(test):advance"])
		self.focus.return_value = obj
		script = scriptHandler._getObjScript(obj, gesture, [])
		assert script is not None
		self.assertEqual(
			script.resumeSayAllMode,
			LegacyWord.script_nextParagraph.__wrapped__.resumeSayAllMode,
		)
		script(gesture)
		gesture.send.assert_not_called()
		self.plugin._playBoundarySound.assert_called_once_with("next")

	def test_legacy_user_gesture_map_resolves_wrapped_native_script(self):
		provider = WordProvider()
		obj = wordObject(LegacyWord, provider)
		gesture = KeyboardInputGesture.fromName("f8")
		self.focus.return_value = obj
		script = scriptHandler._getObjScript(obj, gesture, [(LegacyWord, "previousParagraph")])
		assert script is not None
		script(gesture)
		self.plugin._playBoundarySound.assert_called_once_with("previous")

	def test_native_caret_wait_interrupted_by_script_or_focus_does_not_report(self):
		for interruption in ("script", "focus"):
			with self.subTest(interruption=interruption):
				provider = WordProvider()
				obj = wordObject(UIAWord, provider)
				gesture = KeyboardInputGesture.fromName("downArrow")
				self.focus.return_value = obj
				if interruption == "script":
					self.startPatch(scriptHandler, "_numScriptsQueued", new=0)
					gesture.send = Mock(side_effect=lambda: setattr(scriptHandler, "_numScriptsQueued", 1))
				else:
					gesture.send = Mock(side_effect=lambda: setattr(self.pending, "return_value", True))
				obj.script_caret_moveByLine(gesture)
				self.plugin._playBoundarySound.assert_not_called()
				scriptHandler._numScriptsQueued = 0
				self.pending.return_value = False

	def test_editable_caret_wait_interruption_does_not_report(self):
		with patch.object(scriptHandler, "_numScriptsQueued", 0):
			for interruption in (None, "script", "pendingFocus", "focus"):
				with self.subTest(interruption=interruption):
					obj = EditableProvider(text="abc")
					self.focus.return_value = obj
					self.pending.return_value = False
					scriptHandler._numScriptsQueued = 0
					gesture = KeyboardInputGesture.fromName("upArrow")

					def send():
						if interruption == "script":
							scriptHandler._numScriptsQueued = 1
						elif interruption == "pendingFocus":
							self.pending.return_value = True
						elif interruption == "focus":
							self.focus.return_value = None

					gesture.send = Mock(side_effect=send)
					self.plugin._playBoundarySound.reset_mock()
					obj.script_caret_moveByLine(gesture)
					if interruption is None:
						self.plugin._playBoundarySound.assert_called_once()
					else:
						self.plugin._playBoundarySound.assert_not_called()

	def test_paragraph_without_text_info_reads_current_item_only_at_boundary(self):
		obj = BasicTextProvider(text="one\ntwo")
		obj.role = controlTypes.Role.EDITABLETEXT
		obj.makeTextInfo = Mock(wraps=obj.makeTextInfo)
		self.focus.return_value = obj
		self.section[self.conf.SCENARIO_PARAGRAPH_NAVIGATION] = 2

		self.assertEqual(paragraphHelper.moveToSingleLineBreakParagraph(True, False), (False, True))
		obj.makeTextInfo.assert_called_once_with(textInfos.POSITION_CARET)
		self.speak.assert_not_called()
		self.plugin._playBoundarySound.assert_not_called()

		obj.makeTextInfo.reset_mock()
		self.assertEqual(paragraphHelper.moveToSingleLineBreakParagraph(True, False), (False, False))
		self.assertEqual(obj.makeTextInfo.call_count, 2)
		self.speak.assert_called_once()
		self.plugin._playBoundarySound.assert_called_once_with("next")

	def test_native_wait_failure_restores_existing_override(self):
		obj = wordObject(UIAWord, WordProvider())
		self.focus.return_value = obj
		originalWait = Mock(side_effect=RuntimeError("native wait failed"))
		obj._hasCaretMoved = originalWait
		gesture = KeyboardInputGesture.fromName("downArrow")
		gesture.send = Mock()
		with self.assertRaisesRegex(RuntimeError, "native wait failed"):
			obj.script_caret_moveByLine(gesture)
		self.assertIs(obj._hasCaretMoved, originalWait)
		gesture.send.assert_called_once_with()
		self.plugin._playBoundarySound.assert_not_called()

	def test_legacy_focus_or_value_change_during_com_move_is_silent(self):
		for change in ("focus", "value"):
			with self.subTest(change=change):
				provider = WordProvider()
				obj = wordObject(LegacyWord, provider)
				self.focus.return_value = obj
				if change == "focus":
					provider.comAction = lambda: setattr(self.focus, "return_value", None)
				else:
					provider.comAction = lambda: setattr(obj, "value", "changed")
				obj.script_nextParagraph(KeyboardInputGesture.fromName("control+downArrow"))
				self.plugin._playBoundarySound.assert_not_called()

	def test_disabled_mode_preserves_native_execution_on_both_backends(self):
		self.section[self.conf.SCENARIO_EDITABLE_TEXT_CARET] = 0
		for cls in (UIAWord, LegacyWord):
			for key in ("downArrow", "control+downArrow"):
				self.runKey(cls, key)
				self.plugin._playBoundarySound.assert_not_called()

	def test_browse_home_end_retain_feedback_when_line_probe_raises(self):
		for method, selection, expected in (
			("script_startOfLine", (0, 0), "previous"),
			("script_endOfLine", (2, 2), "next"),
		):
			with self.subTest(method=method):
				cm = CursorManager(text="abc", selection=selection)
				originalMove = BasicTextInfo.move

				def failLineProbe(info, unit, direction, endPoint=None):
					if unit == textInfos.UNIT_LINE:
						raise RuntimeError("line provider unsupported")
					return originalMove(info, unit, direction, endPoint)

				self.plugin._playBoundarySound.reset_mock()
				with patch.object(BasicTextInfo, "move", failLineProbe):
					getattr(cm, method)(None)
				self.plugin._playBoundarySound.assert_called_once_with(expected)

	def test_lifecycle_restores_methods_and_existing_and_new_legacy_gesture_maps(self):
		# Terminate the plugin created in setUp so the first object predates hooks.
		self.plugin.terminate()
		before = wordObject(LegacyWord, WordProvider())
		self.focus.return_value = before
		with patch.dict(IAccessibleHandler.liveNVDAObjectTable, {(1, -4, 0): before}):
			original = LegacyWord.script_nextParagraph
			originalWait = editableText.EditableText._caretMovementScriptHelper
			plugin = self.module.GlobalPlugin()
			try:
				plugin._playBoundarySound = Mock()
				gesture = KeyboardInputGesture.fromName("control+downArrow")
				script = before.getScript(gesture)
				assert script is not None
				script(gesture)
				plugin._playBoundarySound.assert_called_once_with("next")
				after = wordObject(LegacyWord, WordProvider())
				IAccessibleHandler.liveNVDAObjectTable[(2, -4, 0)] = after
			finally:
				plugin.terminate()
			self.assertIs(LegacyWord.script_nextParagraph, original)
			self.assertIs(editableText.EditableText._caretMovementScriptHelper, originalWait)
			self.assertIs(cast(Any, before.getScript(gesture)).__func__, original)
			self.assertIs(cast(Any, after.getScript(gesture)).__func__, original)
