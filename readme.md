# Object Boundary Feedback

Object Boundary Feedback is an NVDA add-on that plays short tones when common
navigation commands reach a boundary.

By default, the add-on replaces supported NVDA boundary messages with the
current item plus a short sound where the current item matches the navigation
unit. For browse mode quick navigation, the add-on keeps NVDA's target-specific
message and adds a short sound. This can be changed in NVDA Settings, Object
Boundary Feedback.

## Covered scenarios

* Review cursor movement by line, page, word, and character when it reaches the
  top, bottom, left, or right boundary.
* Object navigation when there is no containing object, no next object, no
  previous object, or no objects inside.
* Moving the navigator object to the next or previous object in a flattened view
  of the object navigation hierarchy when there is no next or previous object.
* Review mode switching when there is no next or previous review mode.
* Browse mode single letter navigation when no matching previous or next element
  is found.
* Moving past the end of a browse mode container element, such as a list or
  table, when this lands at the bottom of the document.
* Paragraph navigation when there is no next or previous paragraph.
* Browse mode virtual cursor movement or editable text caret movement when the
  cursor cannot move past a boundary.

The add-on does not currently cover ordinary lists, combo boxes, tree views, or
similar objects.

## Settings

Review mode, object navigation, review cursor, browse mode container, and
paragraph navigation boundaries can be set to one of four feedback modes:

* NVDA default.
* Current item.
* Current item and sound.
* NVDA default and sound.

Browse mode quick navigation uses three modes: NVDA default, sound only, or NVDA
default and sound.

Browse mode virtual cursor movement and editable text caret movement use two
modes: NVDA default, or NVDA default and sound.
