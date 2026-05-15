# A part of Object Boundary Feedback
# Copyright (C) 2026 Cary-rowen <manchen_0528@outlook.com>
# This file may be used under the terms of the GNU General Public License, version 2 or later.
# For more details see: https://www.gnu.org/licenses/gpl-2.0.html
# pyright: basic

from __future__ import annotations

from enum import unique
from typing import Any, NamedTuple, cast

import addonHandler
import config
from utils.displayString import DisplayStringIntEnum


addonHandler.initTranslation()


CONF_SECTION = "objBoundaryFeedback"

SCENARIO_REVIEW_MODE = "reviewModeBoundaries"
SCENARIO_OBJECT_NAVIGATION = "objectNavigationBoundaries"
SCENARIO_REVIEW_CURSOR = "reviewCursorBoundaries"
SCENARIO_BROWSE_MODE_QUICK_NAV = "browseModeQuickNavigationBoundaries"
SCENARIO_BROWSE_MODE_CONTAINER_END = "browseModeContainerEndBoundary"
SCENARIO_BROWSE_MODE_VIRTUAL_CURSOR = "browseModeVirtualCursorMovementBoundaries"
SCENARIO_PARAGRAPH_NAVIGATION = "paragraphNavigationBoundaries"
SCENARIO_EDITABLE_TEXT_CARET = "editableTextCaretBoundaries"


@unique
class BoundaryFeedbackMode(DisplayStringIntEnum):
	NVDA_DEFAULT = 0
	CURRENT_ITEM = 1
	CURRENT_ITEM_AND_SOUND = 2
	NVDA_AND_SOUND = 3
	SOUND_ONLY = 4

	@property
	def _displayStringLabels(self) -> dict[BoundaryFeedbackMode, str]:
		return {
			# Translators: Setting option to keep NVDA's normal boundary feedback unchanged.
			BoundaryFeedbackMode.NVDA_DEFAULT: _("NVDA default"),
			# Translators: Setting option to report the current item instead of NVDA's boundary message.
			BoundaryFeedbackMode.CURRENT_ITEM: _("Current item"),
			# Translators: Setting option to report the current item and play a boundary sound.
			BoundaryFeedbackMode.CURRENT_ITEM_AND_SOUND: _("Current item and sound"),
			# Translators: Setting option to keep NVDA's boundary message and also play a sound.
			BoundaryFeedbackMode.NVDA_AND_SOUND: _("NVDA default and sound"),
			# Translators: Setting option to play only a sound at the boundary.
			BoundaryFeedbackMode.SOUND_ONLY: _("Sound only"),
		}


class ScenarioSetting(NamedTuple):
	key: str
	label: str
	modes: tuple[BoundaryFeedbackMode, ...]
	default: BoundaryFeedbackMode


FOUR_MODE_OPTIONS = (
	BoundaryFeedbackMode.NVDA_DEFAULT,
	BoundaryFeedbackMode.CURRENT_ITEM,
	BoundaryFeedbackMode.CURRENT_ITEM_AND_SOUND,
	BoundaryFeedbackMode.NVDA_AND_SOUND,
)
TWO_MODE_OPTIONS = (
	BoundaryFeedbackMode.NVDA_DEFAULT,
	BoundaryFeedbackMode.NVDA_AND_SOUND,
)
THREE_MODE_OPTIONS = (
	BoundaryFeedbackMode.NVDA_DEFAULT,
	BoundaryFeedbackMode.SOUND_ONLY,
	BoundaryFeedbackMode.NVDA_AND_SOUND,
)


SCENARIO_SETTINGS = (
	ScenarioSetting(
		SCENARIO_REVIEW_MODE,
		# Translators: Setting label for boundary feedback when switching review modes.
		_("Review mode boundaries"),
		FOUR_MODE_OPTIONS,
		BoundaryFeedbackMode.CURRENT_ITEM_AND_SOUND,
	),
	ScenarioSetting(
		SCENARIO_OBJECT_NAVIGATION,
		# Translators: Setting label for boundary feedback during object navigation.
		_("Object navigation boundaries"),
		FOUR_MODE_OPTIONS,
		BoundaryFeedbackMode.CURRENT_ITEM_AND_SOUND,
	),
	ScenarioSetting(
		SCENARIO_REVIEW_CURSOR,
		# Translators: Setting label for boundary feedback when moving the review cursor.
		_("Review cursor boundaries"),
		FOUR_MODE_OPTIONS,
		BoundaryFeedbackMode.CURRENT_ITEM_AND_SOUND,
	),
	ScenarioSetting(
		SCENARIO_BROWSE_MODE_QUICK_NAV,
		# Translators: Setting label for boundary feedback in browse mode quick navigation.
		_("Browse mode quick navigation boundaries"),
		THREE_MODE_OPTIONS,
		BoundaryFeedbackMode.NVDA_AND_SOUND,
	),
	ScenarioSetting(
		SCENARIO_BROWSE_MODE_CONTAINER_END,
		# Translators: Setting label for boundary feedback when moving past the end of a browse mode container.
		_("Browse mode container end boundary"),
		FOUR_MODE_OPTIONS,
		BoundaryFeedbackMode.CURRENT_ITEM_AND_SOUND,
	),
	ScenarioSetting(
		SCENARIO_BROWSE_MODE_VIRTUAL_CURSOR,
		# Translators: Setting label for boundary feedback when browse mode virtual cursor movement fails.
		_("Browse mode virtual cursor movement boundaries"),
		TWO_MODE_OPTIONS,
		BoundaryFeedbackMode.NVDA_AND_SOUND,
	),
	ScenarioSetting(
		SCENARIO_PARAGRAPH_NAVIGATION,
		# Translators: Setting label for boundary feedback during paragraph navigation.
		_("Paragraph navigation boundaries"),
		FOUR_MODE_OPTIONS,
		BoundaryFeedbackMode.CURRENT_ITEM_AND_SOUND,
	),
	ScenarioSetting(
		SCENARIO_EDITABLE_TEXT_CARET,
		# Translators: Setting label for boundary feedback when editable text caret movement fails.
		_("Editable text caret boundaries"),
		TWO_MODE_OPTIONS,
		BoundaryFeedbackMode.NVDA_AND_SOUND,
	),
)

SCENARIO_BY_KEY = {setting.key: setting for setting in SCENARIO_SETTINGS}
MAX_MODE_VALUE = max(mode.value for mode in BoundaryFeedbackMode)

confspec = {
	setting.key: f"integer(0, {MAX_MODE_VALUE}, default={setting.default.value})"
	for setting in SCENARIO_SETTINGS
}


def installConfigSpec() -> None:
	cast(Any, config.conf).spec[CONF_SECTION] = confspec
	getAddonConfigSection()


def getAddonConfigSection() -> Any:
	conf = cast(Any, config.conf)
	if CONF_SECTION not in conf:
		conf[CONF_SECTION] = {}
	section = conf[CONF_SECTION]
	for setting in SCENARIO_SETTINGS:
		if setting.key not in section:
			section[setting.key] = setting.default.value
	return section


def getScenarioMode(key: str) -> BoundaryFeedbackMode:
	setting = SCENARIO_BY_KEY[key]
	section = getAddonConfigSection()
	try:
		mode = BoundaryFeedbackMode(int(section[key]))
	except (KeyError, TypeError, ValueError):
		return setting.default
	return mode if mode in setting.modes else setting.default


def modePlaysSound(mode: BoundaryFeedbackMode) -> bool:
	return mode in (
		BoundaryFeedbackMode.CURRENT_ITEM_AND_SOUND,
		BoundaryFeedbackMode.NVDA_AND_SOUND,
		BoundaryFeedbackMode.SOUND_ONLY,
	)


def modeReportsCurrentItem(mode: BoundaryFeedbackMode) -> bool:
	return mode in (BoundaryFeedbackMode.CURRENT_ITEM, BoundaryFeedbackMode.CURRENT_ITEM_AND_SOUND)
