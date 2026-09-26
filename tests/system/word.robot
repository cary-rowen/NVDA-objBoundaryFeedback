*** Settings ***
Documentation    Real Word focus-mode boundary regressions; an installed Word is required.
Library    NvdaLib.py
Library    WordBoundaryLib.py
Test Tags    wordBoundary
Test Teardown    Stop Word Test

*** Test Cases ***
UIA empty
    [Setup]    Start Word Test    UIA
    Verify Word Boundaries    empty
UIA single line
    [Setup]    Start Word Test    UIA
    Verify Word Boundaries    single
UIA paragraphs
    [Setup]    Start Word Test    UIA
    Verify Word Boundaries    paragraphs
UIA wrapped paragraph
    [Setup]    Start Word Test    UIA
    Verify Word Boundaries    wrapped
UIA blank final paragraph
    [Setup]    Start Word Test    UIA
    Verify Word Boundaries    blank-final
UIA manual line breaks
    [Setup]    Start Word Test    UIA
    Verify Word Boundaries    manual-breaks
UIA movement and selection
    [Setup]    Start Word Test    UIA
    Verify Successful Moves And Selection
UIA feedback disabled
    [Setup]    Start Word Test    UIA
    Verify Disabled Feedback
Legacy empty
    [Setup]    Start Word Test    Legacy
    Verify Word Boundaries    empty
Legacy single line
    [Setup]    Start Word Test    Legacy
    Verify Word Boundaries    single
Legacy paragraphs
    [Setup]    Start Word Test    Legacy
    Verify Word Boundaries    paragraphs
Legacy wrapped paragraph
    [Setup]    Start Word Test    Legacy
    Verify Word Boundaries    wrapped
Legacy blank final paragraph
    [Setup]    Start Word Test    Legacy
    Verify Word Boundaries    blank-final
Legacy manual line breaks
    [Setup]    Start Word Test    Legacy
    Verify Word Boundaries    manual-breaks
Legacy movement and selection
    [Setup]    Start Word Test    Legacy
    Verify Successful Moves And Selection
Legacy feedback disabled
    [Setup]    Start Word Test    Legacy
    Verify Disabled Feedback
