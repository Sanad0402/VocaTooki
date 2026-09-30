"""Kideo Land: what differs from Voca Tooki, and nothing else.

The activity and exam SOLVERS are shared with Voca Tooki (vocatooki/solvers/):
both games ship the same com.kideo.learn.english.* activities. This package only
holds the Kideo Land flow around them:

    names         scene and object names (one place to fix when the app moves)
    login         Login/Fitter -> the shared login fields -> first-entry popup
    navigation    start scene islands -> island map -> lessons, levels, exam icons
    level_play    word list -> slot machine -> activity selection -> each activity
    exam          the lesson's exam, solved by the shared exam-page solvers
    lessons       lesson runs by mode, respecting "the exam unlocks the next lesson"

Everything is pressed by OBJECT -- a named Button, an EventTrigger object, or a
component method -- never at a screen coordinate.
"""
