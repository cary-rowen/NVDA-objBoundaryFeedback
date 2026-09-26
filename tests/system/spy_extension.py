# Copyright (C) 2026
# This file is covered by the GNU General Public License, version 2 or later.
# pyright: basic
"""Appended to the official speech spy ONLY in the isolated Robot profile.

Observe real sound playback without replacing caret movement, selection,
providers, or the add-on's boundary decision. Boundary inspection runs on NVDA's
main thread. The installed user's profile is never modified.
"""

import os
import threading
from typing import Any, cast

import globalPluginHandler
import queueHandler


def _boundary_probe(self, clear=False, mode=-1, focus_window=0):
	import api
	import config
	import nvwave
	import textInfos
	import winUser
	from NVDAObjects.IAccessible.winword import WordDocument as LegacyWord
	from NVDAObjects.UIA.wordDocument import WordDocument as UIAWord

	finished = threading.Event()
	result = {}

	def inspect():
		try:
			if focus_window:
				winUser.setForegroundWindow(int(focus_window))
			plugins = [
				plugin
				for plugin in globalPluginHandler.runningPlugins
				if plugin.__module__ == "globalPlugins.objBoundaryFeedback"
			]
			if len(plugins) != 1:
				raise AssertionError("Packaged boundary add-on did not load")
			if not hasattr(self, "_boundary_waves"):
				self._boundary_waves = []
				original = nvwave.playWaveFile

				def record(path, *args, **kwargs):
					if "objBoundaryFeedback" in str(path):
						self._boundary_waves.append(os.path.basename(path))
					return original(path, *args, **kwargs)

				nvwave.playWaveFile = record
			if clear:
				self._boundary_waves.clear()
			if int(mode) >= 0:
				cast(Any, config.conf["objBoundaryFeedback"])["editableTextCaretBoundaries"] = int(mode)
			obj = api.getFocusObject()
			backend = (
				"UIA" if isinstance(obj, UIAWord) else "Legacy" if isinstance(obj, LegacyWord) else "other"
			)
			result.update(
				backend=backend,
				foreground=winUser.getForegroundWindow(),
				focusRoot=winUser.getAncestor(cast(Any, obj).windowHandle, 2),
				foregroundName=api.getForegroundObject().name,
				focusName=obj.name,
				classes=[f"{cls.__module__}.{cls.__name__}" for cls in type(obj).__mro__],
				waves=list(self._boundary_waves),
				focusMode=not obj.treeInterceptor or obj.treeInterceptor.passThrough,
			)
			if backend != "other":
				result["collapsed"] = cast(Any, obj.makeTextInfo(textInfos.POSITION_SELECTION)).isCollapsed
		except Exception as error:
			result["error"] = repr(error)
		finally:
			finished.set()

	queueHandler.queueFunction(queueHandler.eventQueue, inspect)
	# Installed NVDA disables assert statements; waiting must always execute.
	if not finished.wait(10):
		raise AssertionError("NVDA main thread did not respond")
	if "error" in result:
		raise AssertionError(result["error"])
	return result


def install(spy_class):
	spy_class.boundary_probe = _boundary_probe


install(globals()["NVDASpyLib"])
