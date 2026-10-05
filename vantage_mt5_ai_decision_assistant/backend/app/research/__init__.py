"""Offline strategy research — replay engines on history and measure real edge.

Nothing in this package runs inside the live API process; it is used by
``python -m app.research.cli`` to produce ``strategy_scorecard.json``,
which the live backend reads through ``app.evidence``.
"""
