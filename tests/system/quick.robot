*** Settings ***
Documentation    Short acceptance flow: one real Word session for each required backend.
Library    NvdaLib.py
Library    WordBoundaryLib.py
Test Tags    wordBoundary    quick
Test Teardown    Stop Word Test

*** Test Cases ***
UIA quick regression
    [Setup]    Start Word Test    UIA
    Verify Word Boundaries    single
    Verify Word Boundaries    paragraphs
    Verify Successful Moves And Selection
    Verify Disabled Feedback
Legacy quick regression
    [Setup]    Start Word Test    Legacy
    Verify Word Boundaries    single
    Verify Word Boundaries    paragraphs
    Verify Successful Moves And Selection
    Verify Disabled Feedback
