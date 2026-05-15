# A part of Object Boundary Feedback
# Copyright (C) 2026 Cary-rowen <manchen_0528@outlook.com>
# This file may be used under the terms of the GNU General Public License, version 2 or later.
# For more details see: https://www.gnu.org/licenses/gpl-2.0.html
# pyright: basic

from __future__ import annotations

import addonHandler
import wx  # type: ignore[reportMissingImports]
from gui import guiHelper
from gui.settingsDialogs import SettingsPanel

from . import addonConfig


addonHandler.initTranslation()


class BoundaryFeedbackSettingsPanel(SettingsPanel):
	# Translators: Title of the NVDA settings panel for this add-on.
	title = _("Object Boundary Feedback")

	def makeSettings(self, settingsSizer: wx.BoxSizer) -> None:
		settingsSizerHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		# Translators: Label for the group of boundary feedback settings.
		groupSizer = wx.StaticBoxSizer(wx.VERTICAL, self, label=_("Boundary feedback"))
		group = guiHelper.BoxSizerHelper(self, sizer=groupSizer)
		settingsSizerHelper.addItem(group, flag=wx.EXPAND)

		self._controls: dict[str, wx.Choice] = {}
		for setting in addonConfig.SCENARIO_SETTINGS:
			choices = [mode.displayString for mode in setting.modes]
			choice = group.addLabeledControl(
				f"{setting.label}:",
				wx.Choice,
				choices=choices,
			)
			currentMode = addonConfig.getScenarioMode(setting.key)
			choice.SetSelection(setting.modes.index(currentMode))
			self._controls[setting.key] = choice

	def onSave(self) -> None:
		section = addonConfig.getAddonConfigSection()
		for setting in addonConfig.SCENARIO_SETTINGS:
			selection = self._controls[setting.key].GetSelection()
			section[setting.key] = setting.modes[selection].value
