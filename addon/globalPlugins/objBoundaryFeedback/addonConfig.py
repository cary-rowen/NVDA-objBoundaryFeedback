# pyright: basic

from __future__ import annotations

from enum import IntEnum
from typing import Any, NamedTuple, cast

import addonHandler
import config


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


class BoundaryFeedbackMode(IntEnum):
	NVDA_DEFAULT = 0
	CURRENT_ITEM = 1
	CURRENT_ITEM_AND_SOUND = 2
	NVDA_AND_SOUND = 3
	SOUND_ONLY = 4


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


MODE_LABELS = {
	BoundaryFeedbackMode.NVDA_DEFAULT: _("NVDA default"),
	BoundaryFeedbackMode.CURRENT_ITEM: _("Current item"),
	BoundaryFeedbackMode.CURRENT_ITEM_AND_SOUND: _("Current item and sound"),
	BoundaryFeedbackMode.NVDA_AND_SOUND: _("NVDA default and sound"),
	BoundaryFeedbackMode.SOUND_ONLY: _("Sound only"),
}


SCENARIO_SETTINGS = (
	ScenarioSetting(
		SCENARIO_REVIEW_MODE,
		_("Review mode boundaries"),
		FOUR_MODE_OPTIONS,
		BoundaryFeedbackMode.CURRENT_ITEM_AND_SOUND,
	),
	ScenarioSetting(
		SCENARIO_OBJECT_NAVIGATION,
		_("Object navigation boundaries"),
		FOUR_MODE_OPTIONS,
		BoundaryFeedbackMode.CURRENT_ITEM_AND_SOUND,
	),
	ScenarioSetting(
		SCENARIO_REVIEW_CURSOR,
		_("Review cursor boundaries"),
		FOUR_MODE_OPTIONS,
		BoundaryFeedbackMode.CURRENT_ITEM_AND_SOUND,
	),
	ScenarioSetting(
		SCENARIO_BROWSE_MODE_QUICK_NAV,
		_("Browse mode quick navigation boundaries"),
		THREE_MODE_OPTIONS,
		BoundaryFeedbackMode.NVDA_AND_SOUND,
	),
	ScenarioSetting(
		SCENARIO_BROWSE_MODE_CONTAINER_END,
		_("Browse mode container end boundary"),
		FOUR_MODE_OPTIONS,
		BoundaryFeedbackMode.CURRENT_ITEM_AND_SOUND,
	),
	ScenarioSetting(
		SCENARIO_BROWSE_MODE_VIRTUAL_CURSOR,
		_("Browse mode virtual cursor movement boundaries"),
		TWO_MODE_OPTIONS,
		BoundaryFeedbackMode.NVDA_AND_SOUND,
	),
	ScenarioSetting(
		SCENARIO_PARAGRAPH_NAVIGATION,
		_("Paragraph navigation boundaries"),
		FOUR_MODE_OPTIONS,
		BoundaryFeedbackMode.CURRENT_ITEM_AND_SOUND,
	),
	ScenarioSetting(
		SCENARIO_EDITABLE_TEXT_CARET,
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
