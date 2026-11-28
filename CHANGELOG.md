# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Project scaffold: packaging, quality gates, git hooks and continuous integration.
- Documentation site, release workflow, Renovate configuration, pull-request labels and issue templates.
- HTTP transport: per-host pacing, retries honouring `Retry-After`, a stop after ten failures in a row, and secrets kept out of errors and logs.
- Steam endpoints for milestone 1, needing no login: the catalog listing, store items, lookups, exact review totals, the review histogram, current players, profile resolution, wishlists and followed apps. Their answers are validated by payload models that report any field Steam adds.
- Raw archive: the latest answer per source, kind, key and country, compressed, in a per-profile SQLite file.
- Database schema, part 1: lookups, apps, classification and credits, as the notebooks have them, dropped and recreated empty whenever their schema changes.
- Database schema, part 2: relations, offers, media, store lists, requirements, reviews, the wishlist and followed apps.
- Reports: app scores, games, the wishlist and followed apps, computed by the application and written into the database as views.
- Loader: fills the database from the raw archive, loading only what changed, and reports the fields nothing stores, the values that don't follow and the answers it skipped.
- Profiles and the sync: settings per profile, and a sync that fetches only what is stale, archives as it goes and loads after each step.
- Loader: soundtracks' tracks and credits, season-pass backfilled releases, review histogram events, the Steam Deck review's announcement, a video's running time and an app's first franchise.
