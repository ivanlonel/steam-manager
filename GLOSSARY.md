# steam-manager

A local application that gathers one Steam account's store and account data into a database and
helps its owner manage that account.

## Language

### Accounts and storage

**Profile**:
One Steam account's local data: its database, its raw archive and its settings.
_Avoid_: User, account (for the local data), workspace

**Raw archive**:
The compressed, unmodified answers a source returned, kept so the database can be rebuilt.
_Avoid_: Cache, dump, raw store

**Answer**:
What one source returned for one key, in one country when it depends on one: the unit the raw
archive keeps.
_Avoid_: Response, record

**Source**:
A place raw answers come from: the Steam store, HowLongToBeat, Kaggle files or the Steam client
protocol.
_Avoid_: Provider, backend, fetcher

**Sync**:
Fetching what is stale from the sources into the raw archive and loading it into the database.
_Avoid_: Refresh, update, pull

**Rebuild**:
Replaying the raw archive through the loader without contacting any source.
_Avoid_: Reload, regenerate, reindex

**Report**:
A named table of results over the database, such as the games or the wishlist, which the
application computes and also writes into the database as a view.
_Avoid_: View (for the report itself), tab

### Store data

**App**:
Anything Steam identifies by an appid: a game, DLC, demo, mod, software or playtest.
_Avoid_: Game (unless it really is one), title, product

**Catalog**:
The apps a profile knows about, together with their store data.
_Avoid_: Library (that is the owned apps), store, index

**Light entry**:
A catalog app holding only its name, type and review summary.
_Avoid_: Stub, partial app

**Full entry**:
A catalog app holding everything the store returns for it.
_Avoid_: Detailed app, complete record

**Offer**:
A package or bundle, identified by its kind and id, which is what a price belongs to.
_Avoid_: Purchase option (Steam's name for an offer listed under one app), product, item

**Home country**:
The store country a profile asks first.
_Avoid_: Region, locale, primary country

**Fallback country**:
A store country asked, in order, only for apps the home country doesn't sell.
_Avoid_: Secondary region, alternate store

**Store category**:
A Steam store feature flag on an app, such as single-player or full controller support.
_Avoid_: Feature, tag, category (unqualified)

### The account

**Account apps**:
The apps tied to the account: on its wishlist, in its library, followed, ignored, or given a
tracking status or custom list by the user.
_Avoid_: My games, user apps, owned apps

**Library**:
The apps the account owns.
_Avoid_: Collection, owned list, catalog

**Wishlist category**:
A grouping the user created on Steam for wishlist items.
_Avoid_: List, tag, status

**Library collection**:
A grouping the user created in the Steam client for library apps.
_Avoid_: Category, list, folder

**Tracking status**:
The user's single, optional state for an app, chosen from a set the user can customize.
_Avoid_: Category, list, collection, state

**Custom list**:
A named set of apps defined by the user in steam-manager; an app can be in many.
_Avoid_: Category, collection, tag, tracking status

**Change event**:
A persisted record that a sync saw an app released, leave Early Access, get delisted, change its
original price, or gain DLC while owned.
_Avoid_: History, snapshot, log entry
