# Object Boundary Feedback

Object Boundary Feedback is an NVDA add-on that plays short tones when common
navigation commands reach a boundary.

By default, the add-on replaces supported NVDA boundary messages with the
current item plus a short sound where the current item matches the navigation
unit. For browse mode quick navigation, the add-on keeps NVDA's target-specific
message and adds a short sound. This can be changed in NVDA Settings, Object
Boundary Feedback.

## Covered scenarios

* Review cursor boundaries by line, page, word, and character.
* Object navigation boundaries for parent, next, previous, first child, next in
  flow, and previous in flow.
* Review mode next and previous boundaries.
* Browse mode quick navigation when no matching element is found.
* Browse mode virtual cursor movement when the selection does not move.
* Paragraph navigation when NVDA's paragraph helpers report no movement.
* Editable text caret movement when the caret does not move.

The add-on intentionally does not cover ordinary application lists or file views
where the application consumes navigation keys and NVDA receives no explicit
failure signal.

## Settings

Review mode, object navigation, review cursor, and browse mode container
boundaries can be set to one of four feedback modes:

* NVDA default.
* Current item.
* Current item and sound.
* NVDA default and sound.

Browse mode quick navigation uses three modes: NVDA default, sound only, or NVDA
default and sound.

Browse mode virtual cursor movement, paragraph navigation, and editable text
caret movement use two modes: NVDA default, or NVDA default and sound.
