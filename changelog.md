## Unreleased

* Fix incorrect top boundary sounds and missing bottom boundary sounds when
  using Up/Down or Control+Up/Down in Word focus mode.
* Cover both Word UIA navigation and Legacy IAccessible paragraph scripts,
  using the attempted direction and actual caret result for Word vertical navigation.
* Avoid false boundary sounds when collapsing selections, changing focus, or
  interrupting navigation with another queued command.
* Preserve existing browse-mode fallback behavior and boundary detection in
  other controls and navigation commands.

## 0.2.1

Improve sound file.
