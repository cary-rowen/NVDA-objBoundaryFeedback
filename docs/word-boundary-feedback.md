# Word focus-mode boundary feedback: revised design

This revision addresses the two review findings on PR #4. The earlier change
missed Legacy Word paragraph navigation and changed a fallback used by browse
mode. Both findings were valid; the new change preserves the original shared
helpers and adds handling specifically for Word vertical caret movement.

## Why the original detection fails

An unchanged caret does not identify the direction the user attempted. Probing
`TextInfo.move(unit, -1)` and `move(unit, 1)` afterwards measures provider range
movement, which can differ from keyboard navigation at Word's last line or
paragraph. It can therefore infer the top boundary for a downward gesture or
miss the bottom boundary when both range probes succeed.

Microsoft documents range movement separately from keyboard navigation:
[ITextRangeProvider::Move](https://learn.microsoft.com/en-us/windows/win32/api/uiautomationcore/nf-uiautomationcore-itextrangeprovider-move).
NVDA's Word implementations also contain provider-specific range handling:
[UIA Word TextInfo](https://github.com/nvaccess/nvda/blob/f62c980589d1ac30babf68ad48177e9ad29a2e84/source/NVDAObjects/UIA/wordDocument.py)
and [Legacy Word TextInfo](https://github.com/nvaccess/nvda/blob/f62c980589d1ac30babf68ad48177e9ad29a2e84/source/NVDAObjects/window/winword.py).

## Two native paths, one reporting rule

| Native route | Observation | Direction |
| --- | --- | --- |
| Word Up/Down; UIA Word application-handled Ctrl+Up/Down | Observe NVDA's existing `_hasCaretMoved` result, copying the caret before speech expands it | The normalized Up/Down gesture |
| Legacy Word `script_previousParagraph` / `script_nextParagraph` | Call the original script once and read the caret after its synchronous COM movement | The native script's direction, including remapped gestures |

The distinction is visible in the official source:
[EditableText send/wait/report sequence](https://github.com/nvaccess/nvda/blob/f62c980589d1ac30babf68ad48177e9ad29a2e84/source/editableText.py#L154-L180)
and [Legacy Word paragraph scripts](https://github.com/nvaccess/nvda/blob/f62c980589d1ac30babf68ad48177e9ad29a2e84/source/NVDAObjects/IAccessible/winword.py#L472-L492).
Legacy paragraph scripts call `Range.move(wdParagraph, +/-1)` and
`_caretScriptPostMovedHelper` directly. They neither send a keyboard gesture
nor call `_caretMovementScriptHelper`.

For these Word paths, feedback is added only when the initial selection is
collapsed, the observed caret and final selection are unchanged, readable value
snapshots are unchanged, and neither queued navigation nor a focus transition
invalidates the observation. A missing wait result is not a boundary.
The temporary wait observer is restored in `finally`, including an existing
instance override and native exceptions. No extra key, wait, or speculative
line/paragraph range movement is introduced.

Legacy script wrappers retain metadata with `functools.wraps`. Existing Word
objects' cached gesture functions are updated using the add-on's existing
gesture-map replacement mechanism. Its target provider includes the focus,
navigator, and NVDA's live MSAA object cache, and is evaluated again on unload
to restore maps for documents created while the add-on was active. See
[NVDA's instance gesture bindings](https://github.com/nvaccess/nvda/blob/f62c980589d1ac30babf68ad48177e9ad29a2e84/source/baseObject.py#L224-L310).

## Compatibility boundaries

- `_lineBoundaryIsDocumentBoundary`, including its `True` exception fallback,
  is restored exactly to upstream behavior. Browse-mode callers retain their feedback.
- `_directionFromTextBoundary` and `_directionFromEnclosingUnitBoundary` are
  retained. Non-Word controls, other navigation keys, and gestures outside the
  Word vertical-key workaround continue through the original editable hook.
- Object navigation, review navigation, quick navigation, container navigation,
  virtual cursor navigation, paragraph helpers, and scenario settings retain
  their original implementations.
- Native paragraph movement, speech, review, braille and say-all handling remain
  delegated to NVDA. The NVDA-default setting adds no boundary sound.

These address the review on
[Legacy Word coverage](https://github.com/cary-rowen/NVDA-objBoundaryFeedback/pull/4#discussion_r4080684010)
and [browse-mode fallback](https://github.com/cary-rowen/NVDA-objBoundaryFeedback/pull/4#discussion_r4080684456).

## Reproducing automated tests

Native-path tests require Windows and a built official NVDA checkout. Follow
[NVDA's environment requirements](https://github.com/nvaccess/nvda/blob/f62c980589d1ac30babf68ad48177e9ad29a2e84/projectDocs/dev/createDevEnvironment.md)
and [build instructions](https://github.com/nvaccess/nvda/blob/f62c980589d1ac30babf68ad48177e9ad29a2e84/projectDocs/dev/buildingNVDA.md).
CI checks both NVDA 2026.1 and 2026.2.

```powershell
# From the recursive NVDA checkout:
uv sync --frozen --group unit-tests
.\scons.bat source -j 4
# From this add-on checkout; substitute the path to the NVDA checkout:
$nvdaRoot = 'C:\path\to\nvda'
& "$nvdaRoot\.venv\Scripts\python.exe" tests/run_nvda_tests.py --nvda-root $nvdaRoot --output test-results/native
& "$nvdaRoot\.venv\Scripts\python.exe" tests/run_nvda_tests.py --nvda-root $nvdaRoot --output test-results/upstream --upstream
```

The native suite imports the real Word classes, script resolver, caret wait,
post-movement helper, CursorManager, paragraph helpers, configuration and plugin
lifecycle. Application I/O is controlled through NVDA's official unit-test text
provider. It does **not** claim to run real Word UIA/COM servers or desktop keys.
The upstream run loads the add-on with its default modes enabled and suppresses
only actual audio playback. XML reports retain failures and skips. Exploratory
stubs, the real-Word Robot runner, and dated validation notes are archived on
`review/pr5-extra-validation`.

来自 GPT6Astra 驱动的 CODEX
