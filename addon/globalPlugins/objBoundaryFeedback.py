# pyright: basic

from __future__ import annotations

import functools
import inspect
import os
import re
from collections.abc import Callable, Iterable, Iterator
from typing import Any, cast

import api
import browseMode
import config
import controlTypes
import cursorManager
from documentNavigation import paragraphHelper
import editableText
import globalCommands
import globalPluginHandler
from logHandler import log
from NVDAObjects import NVDAObject
import nvwave
import review
import scriptHandler
import textInfos
import treeInterceptorHandler


_PREVIOUS = "previous"
_NEXT = "next"
_GENERIC = "generic"

_WAVE_FILE_BY_DIRECTION = {
	_PREVIOUS: "boundaryPrevious.wav",
	_NEXT: "boundaryNext.wav",
	_GENERIC: "boundaryGeneric.wav",
}

_ADDON_DIR = os.path.dirname(__file__)

_MethodPatch = tuple[Any, str, Callable[..., Any]]
_GestureMapReplacement = tuple[Callable[[], Iterable[Any]], Callable[..., Any], Callable[..., Any]]


def _getConfigValue(section: str, key: str) -> Any:
	return cast(Any, config.conf)[section][key]


def _hasExpectedFunctionSignature(func: Callable[..., Any], expected: tuple[str, ...]) -> bool:
	try:
		actual = tuple(inspect.signature(func).parameters)
	except (TypeError, ValueError):
		log.debugWarning(f"Unable to inspect signature for {func!r}", exc_info=True)
		return False
	if actual != expected:
		log.warning(
			f"Skipping objBoundaryFeedback hook for {func!r}: expected {expected}, got {actual}",
		)
		return False
	return True


def _sameTextRange(first: textInfos.TextInfo, second: textInfos.TextInfo) -> bool:
	try:
		return (
			first.compareEndPoints(second, "startToStart") == 0
			and first.compareEndPoints(second, "endToEnd") == 0
		)
	except Exception:
		log.debugWarning("Unable to compare text ranges for boundary feedback", exc_info=True)
		return False


def _getSelectionRange(obj: cursorManager.CursorManager) -> textInfos.TextInfo | None:
	try:
		return obj.makeTextInfo(textInfos.POSITION_SELECTION).copy()
	except Exception:
		log.debugWarning("Unable to get cursor manager selection for boundary feedback", exc_info=True)
		return None


def _isComboBoxOrDescendant(obj: Any) -> bool:
	for _ in range(3):
		if obj is None:
			return False
		if (
			getattr(obj, "role", None) == controlTypes.Role.COMBOBOX
			or getattr(obj, "windowClassName", None) == "ComboBox"
		):
			return True
		try:
			obj = getattr(obj, "parent", None)
		except Exception:
			log.debugWarning("Unable to inspect editable text parent for boundary feedback", exc_info=True)
			return False
	return False


def _directionFromEnclosingUnitBoundary(info: textInfos.TextInfo, unit: str) -> str | None:
	try:
		collapsedInfo = info.copy()
		collapsedInfo.collapse()
		unitInfo = collapsedInfo.copy()
		unitInfo.expand(unit)
		atStart = collapsedInfo.compareEndPoints(unitInfo, "startToStart") <= 0
		atEnd = collapsedInfo.compareEndPoints(unitInfo, "endToEnd") >= 0
	except Exception:
		log.debugWarning("Unable to infer enclosing text boundary direction", exc_info=True)
		return None
	if atStart == atEnd:
		return _GENERIC if atStart else None
	return _PREVIOUS if atStart else _NEXT


def _directionFromTextBoundary(info: textInfos.TextInfo, unit: str) -> str | None:
	if unit == textInfos.UNIT_CHARACTER:
		lineBoundaryDirection = _directionFromEnclosingUnitBoundary(info, textInfos.UNIT_LINE)
		if lineBoundaryDirection is not None:
			return lineBoundaryDirection
	try:
		previousInfo = info.copy()
		canMovePrevious = previousInfo.move(unit, -1) != 0
		nextInfo = info.copy()
		canMoveNext = nextInfo.move(unit, 1) != 0
	except Exception:
		log.debugWarning("Unable to infer text boundary direction", exc_info=True)
		return _GENERIC
	if canMovePrevious == canMoveNext:
		return None if canMovePrevious else _GENERIC
	return _NEXT if canMovePrevious else _PREVIOUS


def _directionFromBrowseDirection(direction: str) -> str:
	if direction == "previous":
		return _PREVIOUS
	return _NEXT


def _directionFromCursorMovement(
	direction: Any,
	posConstant: Any,
	posUnit: Any,
	posUnitEnd: bool,
) -> str:
	if direction is not None:
		try:
			if direction < 0:
				return _PREVIOUS
			if direction > 0:
				return _NEXT
		except TypeError:
			return _GENERIC
	if posConstant == textInfos.POSITION_FIRST:
		return _PREVIOUS
	if posConstant == textInfos.POSITION_LAST:
		return _NEXT
	if posUnit is not None:
		return _NEXT if posUnitEnd else _PREVIOUS
	return _GENERIC


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self, *args: Any, **kwargs: Any) -> None:
		super().__init__(*args, **kwargs)
		self._methodPatches: list[_MethodPatch] = []
		self._gestureMapReplacements: list[_GestureMapReplacement] = []
		self._installGlobalCommandHooks()
		self._installBrowseModeHooks()
		self._installCursorManagerHook()
		self._installEditableTextHook()
		self._installParagraphHelperHooks()

	def terminate(self) -> None:
		self._restoreGestureMapReplacements()
		for owner, name, original in reversed(self._methodPatches):
			try:
				setattr(owner, name, original)
			except Exception:
				log.debugWarning(
					f"Unable to restore objBoundaryFeedback hook {owner!r}.{name}",
					exc_info=True,
				)
		self._methodPatches.clear()
		self._gestureMapReplacements.clear()
		super().terminate()

	def _playBoundarySound(self, direction: str) -> None:
		fileName = _WAVE_FILE_BY_DIRECTION.get(direction, _WAVE_FILE_BY_DIRECTION[_GENERIC])
		filePath = os.path.join(_ADDON_DIR, fileName)
		try:
			nvwave.playWaveFile(filePath)
		except Exception:
			log.debugWarning(f"Unable to play boundary feedback sound: {filePath}", exc_info=True)

	def _replaceGestureMapFunction(
		self,
		obj: Any,
		original: Callable[..., Any],
		replacement: Callable[..., Any],
	) -> None:
		gestureMap = getattr(obj, "_gestureMap", None)
		if not gestureMap:
			return
		for identifier, func in list(gestureMap.items()):
			if func is original:
				gestureMap[identifier] = replacement

	def _restoreGestureMapReplacements(self) -> None:
		for targetProvider, original, replacement in reversed(self._gestureMapReplacements):
			try:
				targets = targetProvider()
			except Exception:
				log.debugWarning(
					"Unable to get gesture map targets for objBoundaryFeedback restore",
					exc_info=True,
				)
				continue
			for target in targets:
				self._replaceGestureMapFunction(target, replacement, original)

	def _installMethodPatch(
		self,
		owner: Any,
		name: str,
		replacement: Callable[..., Any],
	) -> None:
		original = getattr(owner, name)
		setattr(owner, name, replacement)
		self._methodPatches.append((owner, name, original))

	def _installGlobalCommandHook(
		self,
		name: str,
		boundaryDetector: Callable[[], str | None],
	) -> None:
		original = getattr(globalCommands.GlobalCommands, name, None)
		if original is None:
			log.warning(f"Skipping objBoundaryFeedback hook: GlobalCommands.{name} does not exist")
			return
		if not _hasExpectedFunctionSignature(original, ("self", "gesture")):
			return

		@functools.wraps(original)
		def replacement(commandObj, gesture):
			direction = self._safeDetectBoundary(boundaryDetector)
			original(commandObj, gesture)
			if direction:
				self._playBoundarySound(direction)

		self._installMethodPatch(globalCommands.GlobalCommands, name, replacement)
		self._replaceGestureMapFunction(globalCommands.commands, original, replacement)
		self._gestureMapReplacements.append((lambda: (globalCommands.commands,), original, replacement))

	def _safeDetectBoundary(
		self,
		boundaryDetector: Callable[[], str | None],
	) -> str | None:
		try:
			return boundaryDetector()
		except Exception:
			log.debugWarning("Unable to detect navigation boundary", exc_info=True)
			return None

	def _installGlobalCommandHooks(self) -> None:
		for name, detector in (
			("script_reviewMode_next", self._detectReviewModeNextBoundary),
			("script_reviewMode_previous", self._detectReviewModePreviousBoundary),
			("script_navigatorObject_parent", self._detectNavigatorParentBoundary),
			("script_navigatorObject_next", self._detectNavigatorNextBoundary),
			("script_navigatorObject_previous", self._detectNavigatorPreviousBoundary),
			("script_navigatorObject_firstChild", self._detectNavigatorFirstChildBoundary),
			("script_navigatorObject_nextInFlow", self._detectNavigatorNextInFlowBoundary),
			("script_navigatorObject_previousInFlow", self._detectNavigatorPreviousInFlowBoundary),
			("script_review_previousLine", self._detectReviewPreviousLineBoundary),
			("script_review_nextLine", self._detectReviewNextLineBoundary),
			("script_review_previousPage", self._detectReviewPreviousPageBoundary),
			("script_review_nextPage", self._detectReviewNextPageBoundary),
			("script_review_previousWord", self._detectReviewPreviousWordBoundary),
			("script_review_nextWord", self._detectReviewNextWordBoundary),
			("script_review_previousCharacter", self._detectReviewPreviousCharacterBoundary),
			("script_review_nextCharacter", self._detectReviewNextCharacterBoundary),
		):
			self._installGlobalCommandHook(name, detector)

	def _detectReviewModeNextBoundary(self) -> str | None:
		return None if self._hasAvailableReviewMode(previous=False) else _NEXT

	def _detectReviewModePreviousBoundary(self) -> str | None:
		return None if self._hasAvailableReviewMode(previous=True) else _PREVIOUS

	def _hasAvailableReviewMode(self, previous: bool) -> bool:
		currentMode = review.getCurrentMode()
		modes = review.modes
		currentIndex = next(
			(index for index, mode in enumerate(modes) if mode[0] == currentMode),
			None,
		)
		if currentIndex is None:
			return False
		step = -1 if previous else 1
		index = currentIndex + step
		obj = api.getNavigatorObject()
		while 0 <= index < len(modes):
			modeGetter = modes[index][2]
			if modeGetter(obj):
				return True
			index += step
		return False

	def _isNavigatorRelationMissing(self, simpleAttr: str, fullAttr: str) -> bool:
		curObject = api.getNavigatorObject()
		if not isinstance(curObject, NVDAObject):
			return False
		attr = simpleAttr if bool(_getConfigValue("reviewCursor", "simpleReviewMode")) else fullAttr
		return getattr(curObject, attr) is None

	def _detectNavigatorParentBoundary(self) -> str | None:
		return _PREVIOUS if self._isNavigatorRelationMissing("simpleParent", "parent") else None

	def _detectNavigatorNextBoundary(self) -> str | None:
		return _NEXT if self._isNavigatorRelationMissing("simpleNext", "next") else None

	def _detectNavigatorPreviousBoundary(self) -> str | None:
		return _PREVIOUS if self._isNavigatorRelationMissing("simplePrevious", "previous") else None

	def _detectNavigatorFirstChildBoundary(self) -> str | None:
		return _NEXT if self._isNavigatorRelationMissing("simpleFirstChild", "firstChild") else None

	def _detectNavigatorNextInFlowBoundary(self) -> str | None:
		curObject = api.getNavigatorObject()
		if not isinstance(curObject, NVDAObject):
			return None
		if getattr(curObject, "simpleFirstChild") or getattr(curObject, "simpleNext"):
			return None
		parent = getattr(curObject, "simpleParent")
		while parent and not getattr(parent, "simpleNext"):
			parent = getattr(parent, "simpleParent")
		return None if parent else _NEXT

	def _detectNavigatorPreviousInFlowBoundary(self) -> str | None:
		curObject = api.getNavigatorObject()
		if not isinstance(curObject, NVDAObject):
			return None
		return (
			None if getattr(curObject, "simplePrevious") or getattr(curObject, "simpleParent") else _PREVIOUS
		)

	def _detectReviewPreviousLineBoundary(self) -> str | None:
		info = api.getReviewPosition().copy()
		info.expand(textInfos.UNIT_LINE)
		info.collapse()
		return _PREVIOUS if info.move(textInfos.UNIT_LINE, -1) == 0 else None

	def _detectReviewNextLineBoundary(self) -> str | None:
		origInfo = api.getReviewPosition().copy()
		origInfo.collapse()
		info = origInfo.copy()
		res = info.move(textInfos.UNIT_LINE, 1)
		newLine = info.copy()
		newLine.expand(textInfos.UNIT_LINE)
		return _NEXT if res == 0 or newLine.start <= origInfo.start else None

	def _detectReviewPreviousPageBoundary(self) -> str | None:
		info = api.getReviewPosition().copy()
		try:
			info.expand(textInfos.UNIT_PAGE)
			info.collapse()
			res = info.move(textInfos.UNIT_PAGE, -1)
		except (ValueError, NotImplementedError):
			return None
		return _PREVIOUS if res == 0 else None

	def _detectReviewNextPageBoundary(self) -> str | None:
		origInfo = api.getReviewPosition().copy()
		origInfo.collapse()
		info = origInfo.copy()
		try:
			res = info.move(textInfos.UNIT_PAGE, 1)
			newPage = info.copy()
			newPage.expand(textInfos.UNIT_PAGE)
		except (ValueError, NotImplementedError):
			return None
		return _NEXT if res == 0 or newPage.start <= origInfo.start else None

	def _detectReviewPreviousWordBoundary(self) -> str | None:
		info = api.getReviewPosition().copy()
		info.expand(textInfos.UNIT_WORD)
		info.collapse()
		return _PREVIOUS if info.move(textInfos.UNIT_WORD, -1) == 0 else None

	def _detectReviewNextWordBoundary(self) -> str | None:
		origInfo = api.getReviewPosition().copy()
		origInfo.collapse()
		info = origInfo.copy()
		res = info.move(textInfos.UNIT_WORD, 1)
		newWord = info.copy()
		newWord.expand(textInfos.UNIT_WORD)
		return _NEXT if res == 0 or newWord.start <= origInfo.start else None

	def _detectReviewPreviousCharacterBoundary(self) -> str | None:
		lineInfo = api.getReviewPosition().copy()
		lineInfo.expand(textInfos.UNIT_LINE)
		charInfo = api.getReviewPosition().copy()
		charInfo.expand(textInfos.UNIT_CHARACTER)
		charInfo.collapse()
		res = charInfo.move(textInfos.UNIT_CHARACTER, -1)
		if res == 0 or charInfo.compareEndPoints(lineInfo, "startToStart") < 0:
			return _PREVIOUS
		return None

	def _detectReviewNextCharacterBoundary(self) -> str | None:
		lineInfo = api.getReviewPosition().copy()
		lineInfo.expand(textInfos.UNIT_LINE)
		charInfo = api.getReviewPosition().copy()
		charInfo.expand(textInfos.UNIT_CHARACTER)
		charInfo.collapse()
		res = charInfo.move(textInfos.UNIT_CHARACTER, 1)
		if res == 0 or charInfo.compareEndPoints(lineInfo, "endToEnd") >= 0:
			return _NEXT
		return None

	def _installBrowseModeHooks(self) -> None:
		quickNavOriginal = browseMode.BrowseModeTreeInterceptor._quickNavScript
		if _hasExpectedFunctionSignature(
			quickNavOriginal,
			("self", "gesture", "itemType", "direction", "errorMessage", "readUnit"),
		):
			quickNavReplacement = self._makeQuickNavScriptReplacement(quickNavOriginal)
			self._installMethodPatch(
				browseMode.BrowseModeTreeInterceptor,
				"_quickNavScript",
				quickNavReplacement,
			)

		movePastEndOriginal = getattr(
			browseMode.BrowseModeDocumentTreeInterceptor,
			"script_movePastEndOfContainer",
			None,
		)
		if movePastEndOriginal is None:
			return
		if _hasExpectedFunctionSignature(movePastEndOriginal, ("self", "gesture")):
			movePastEndReplacement = self._makeMovePastEndOfContainerReplacement(movePastEndOriginal)
			self._installMethodPatch(
				browseMode.BrowseModeDocumentTreeInterceptor,
				"script_movePastEndOfContainer",
				movePastEndReplacement,
			)
			self._replaceExistingBrowseModeGestureMaps(movePastEndOriginal, movePastEndReplacement)
			self._gestureMapReplacements.append(
				(
					self._getRunningBrowseModeTreeInterceptors,
					movePastEndOriginal,
					movePastEndReplacement,
				),
			)

	def _makeQuickNavScriptReplacement(self, original):
		@functools.wraps(original)
		def replacement(treeInterceptor, gesture, itemType, direction, errorMessage, readUnit):
			try:
				info = treeInterceptor.selection.copy()
			except Exception:
				info = None
			original(treeInterceptor, gesture, itemType, direction, errorMessage, readUnit)
			if info is None:
				return
			try:
				selection = treeInterceptor.selection.copy()
			except Exception:
				log.debugWarning("Unable to get browse mode selection for boundary feedback", exc_info=True)
				return
			if not _sameTextRange(info, selection):
				return
			if self._isQuickNavBoundary(treeInterceptor, itemType, direction, info):
				self._playBoundarySound(_directionFromBrowseDirection(direction))

		return replacement

	def _iterQuickNavItems(
		self,
		treeInterceptor: browseMode.BrowseModeTreeInterceptor,
		itemType: str,
		direction: str,
		info: textInfos.TextInfo,
	) -> Iterator[Any]:
		if itemType == "notLinkBlock":
			return treeInterceptor._iterNotLinkBlock(direction, info)
		if itemType == "textParagraph":
			punctuationMarksRegex = re.compile(
				str(_getConfigValue("virtualBuffers", "textParagraphRegex")),
			)

			def textParagraphFunc(info: textInfos.TextInfo) -> bool:
				return punctuationMarksRegex.search(info.text) is not None

			return treeInterceptor._iterSimilarParagraph(
				kind="textParagraph",
				paragraphFunction=textParagraphFunc,
				desiredValue=True,
				direction=cast(Any, direction),
				pos=info,
			)
		if itemType == "verticalParagraph":

			def verticalParagraphFunc(info: textInfos.TextInfo) -> int | None:
				try:
					return getattr(info, "location")[0]
				except (AttributeError, TypeError):
					return None

			return treeInterceptor._iterSimilarParagraph(
				kind="verticalParagraph",
				paragraphFunction=verticalParagraphFunc,
				desiredValue=None,
				direction=cast(Any, direction),
				pos=info,
			)
		if itemType in ("sameStyle", "differentStyle"):
			return treeInterceptor._iterTextStyle(itemType, cast(Any, direction), info)
		return treeInterceptor._iterNodesByType(itemType, direction, info)

	def _isQuickNavBoundary(
		self,
		treeInterceptor: browseMode.BrowseModeTreeInterceptor,
		itemType: str,
		direction: str,
		info: textInfos.TextInfo,
	) -> bool:
		try:
			next(self._iterQuickNavItems(treeInterceptor, itemType, direction, info))
		except NotImplementedError:
			return False
		except StopIteration:
			return True
		except Exception:
			log.debugWarning("Unable to detect browse mode quick navigation boundary", exc_info=True)
		return False

	def _makeMovePastEndOfContainerReplacement(self, original):
		@functools.wraps(original)
		def replacement(treeInterceptor, gesture):
			hitBoundary = self._isMovePastEndOfContainerBoundary(treeInterceptor)
			original(treeInterceptor, gesture)
			if hitBoundary:
				self._playBoundarySound(_NEXT)

		return replacement

	def _isMovePastEndOfContainerBoundary(self, treeInterceptor) -> bool:
		try:
			info = treeInterceptor.makeTextInfo(textInfos.POSITION_CARET)
			info.expand(textInfos.UNIT_CHARACTER)
			container = treeInterceptor.getEnclosingContainerRange(info)
			if not container:
				return False
			container.collapse(end=True)
			docEnd = container.obj.makeTextInfo(textInfos.POSITION_LAST)
			return container.compareEndPoints(docEnd, "endToEnd") >= 0
		except Exception:
			log.debugWarning("Unable to detect container end boundary", exc_info=True)
			return False

	def _getRunningBrowseModeTreeInterceptors(self) -> tuple[browseMode.BrowseModeTreeInterceptor, ...]:
		return tuple(
			treeInterceptor
			for treeInterceptor in treeInterceptorHandler.runningTable
			if isinstance(treeInterceptor, browseMode.BrowseModeTreeInterceptor)
		)

	def _replaceExistingBrowseModeGestureMaps(self, original, replacement) -> None:
		for treeInterceptor in self._getRunningBrowseModeTreeInterceptors():
			self._replaceGestureMapFunction(treeInterceptor, original, replacement)

	def _installCursorManagerHook(self) -> None:
		original = cursorManager.CursorManager._caretMovementScriptHelper
		expected = (
			"self",
			"gesture",
			"unit",
			"direction",
			"posConstant",
			"posUnit",
			"posUnitEnd",
			"extraDetail",
			"handleSymbols",
		)
		if not _hasExpectedFunctionSignature(original, expected):
			return

		@functools.wraps(original)
		def replacement(
			cursorManagerObj,
			gesture,
			unit,
			direction=None,
			posConstant=textInfos.POSITION_SELECTION,
			posUnit=None,
			posUnitEnd=False,
			extraDetail=False,
			handleSymbols=False,
		):
			if scriptHandler.isScriptWaiting():
				return original(
					cursorManagerObj,
					gesture,
					unit,
					direction,
					posConstant,
					posUnit,
					posUnitEnd,
					extraDetail,
					handleSymbols,
				)
			before = _getSelectionRange(cursorManagerObj)
			boundaryDirection = _directionFromCursorMovement(direction, posConstant, posUnit, posUnitEnd)
			original(
				cursorManagerObj,
				gesture,
				unit,
				direction,
				posConstant,
				posUnit,
				posUnitEnd,
				extraDetail,
				handleSymbols,
			)
			after = _getSelectionRange(cursorManagerObj)
			if before is not None and after is not None and _sameTextRange(before, after):
				self._playBoundarySound(boundaryDirection)

		self._installMethodPatch(cursorManager.CursorManager, "_caretMovementScriptHelper", replacement)

	def _installEditableTextHook(self) -> None:
		original = editableText.EditableText._caretMovementScriptHelper
		if not _hasExpectedFunctionSignature(original, ("self", "gesture", "unit")):
			return

		@functools.wraps(original)
		def replacement(editableTextObj, gesture, unit):
			try:
				before = editableTextObj.makeTextInfo(textInfos.POSITION_CARET).copy()
			except Exception:
				original(editableTextObj, gesture, unit)
				return
			original(editableTextObj, gesture, unit)
			try:
				after = editableTextObj.makeTextInfo(textInfos.POSITION_CARET).copy()
			except Exception:
				return
			if _sameTextRange(before, after):
				if unit == textInfos.UNIT_LINE and _isComboBoxOrDescendant(editableTextObj):
					return
				boundaryDirection = _directionFromTextBoundary(after, unit)
				if boundaryDirection is not None:
					self._playBoundarySound(boundaryDirection)

		self._installMethodPatch(editableText.EditableText, "_caretMovementScriptHelper", replacement)

	def _installParagraphHelperHooks(self) -> None:
		for name in ("moveToSingleLineBreakParagraph", "moveToMultiLineBreakParagraph"):
			original = getattr(paragraphHelper, name)
			if not _hasExpectedFunctionSignature(original, ("nextParagraph", "speakNew", "ti")):
				continue
			replacement = self._makeParagraphMovementReplacement(original)
			self._installMethodPatch(paragraphHelper, name, replacement)

	def _makeParagraphMovementReplacement(self, original):
		@functools.wraps(original)
		def replacement(nextParagraph: bool, speakNew: bool, ti: textInfos.TextInfo | None = None):
			passKey, moved = original(nextParagraph, speakNew, ti)
			if not passKey and not moved:
				self._playBoundarySound(_NEXT if nextParagraph else _PREVIOUS)
			return passKey, moved

		return replacement
