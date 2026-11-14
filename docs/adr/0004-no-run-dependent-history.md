# No history that depends on when the application ran

The database shows the latest known state only. Price history, playtime snapshots, list
membership over time and review trends are deliberately absent, because what such tables hold
depends on when and how often a profile happened to be synced, not on anything Steam can
reproduce. The single exception is the change feed, which persists five kinds of change event:
an app released, left Early Access, was delisted, changed its original price (discounts are
ignored), or gained DLC while owned.

A tracking status keeps the date the user last changed it; that records a user action, not a
run.
