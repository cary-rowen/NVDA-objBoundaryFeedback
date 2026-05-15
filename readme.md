# Object Boundary Feedback

Object Boundary Feedback is an NVDA add-on that plays short tones when common
navigation commands reach a boundary.

The add-on does not suppress NVDA's existing speech or braille output; it only adds sound
feedback.

## Covered scenarios

* Review cursor boundaries by line, page, word, and character.
* Object navigation boundaries for parent, next, previous, first child, next in
  flow, and previous in flow.
* Review mode next and previous boundaries.
* Browse mode quick navigation when no matching element is found.
* Browse mode virtual cursor movement when the selection does not move.
* Paragraph navigation when NVDA's paragraph helpers report no movement.
* Editable text controls that fire `caretMovementFailed`.

The add-on intentionally does not cover ordinary application lists or file views
where the application consumes navigation keys and NVDA receives no explicit
failure signal.
