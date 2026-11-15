-- The schema of steam-database.ipynb, cell 2, in the owner's steam-collection repository,
-- verbatim. tests/steam_manager/db/schema/_notebook.py compares the declared tables with it.
-- Lookups
CREATE TABLE store_category (
    categoryid INTEGER PRIMARY KEY,
    type INTEGER,  -- 1 players, 2 features, 3 controller, 0 anything else
    internal_name TEXT,
    display_name TEXT,
    image_url TEXT,
    computed INTEGER,
    edit_url TEXT,
    edit_sort_order INTEGER
) STRICT;
CREATE TABLE tag (tagid INTEGER PRIMARY KEY, name TEXT) STRICT;
CREATE TABLE genre (genreid INTEGER PRIMARY KEY, name TEXT) STRICT;
CREATE TABLE language (elanguage INTEGER PRIMARY KEY, name TEXT) STRICT;
CREATE TABLE review_score (review_score INTEGER PRIMARY KEY, label TEXT) STRICT;  -- The label for 0 depends on the count: see v_app_scores
CREATE TABLE rating_agency (agency INTEGER PRIMARY KEY, rating_type TEXT) STRICT;
CREATE TABLE age_rating (
    agency INTEGER NOT NULL REFERENCES rating_agency (agency),
    rating TEXT NOT NULL,
    image_url TEXT,
    PRIMARY KEY (agency, rating)
) STRICT, WITHOUT ROWID;
CREATE TABLE anticheat (name TEXT PRIMARY KEY, name_loc TEXT) STRICT, WITHOUT ROWID;

-- Apps
CREATE TABLE app (
    appid INTEGER PRIMARY KEY,
    name TEXT,
    type INTEGER,  -- 0 game, 1 demo, 2 mod, 4 DLC, 6 software, 12 playtest, 14 some older titles (unconfirmed)
    success INTEGER,  -- 1 found, 15 mostly not sold in that country
    store_url_path TEXT,
    store_url_path_override TEXT,
    store_country TEXT CHECK (store_country IN ('BR', 'US')),
    is_listed INTEGER,  -- Listed on either store, known only for apps from steam-games
    is_free INTEGER,
    unlisted INTEGER,
    unavailable_for_country_restriction INTEGER,
    parent_appid INTEGER REFERENCES app (appid),
    current_players INTEGER,
    steam_release_date TEXT,
    original_release_date TEXT,
    original_steam_release_date TEXT,
    mac_release_date TEXT,
    linux_release_date TEXT,
    release_from_early_access_date TEXT,
    release_from_early_access_style INTEGER,
    is_coming_soon INTEGER,
    is_early_access INTEGER,
    is_preload INTEGER,  -- Steam sends it only when true
    coming_soon_display TEXT,
    custom_release_date_message TEXT,
    free_weekend_start TEXT,
    free_weekend_end TEXT,
    free_weekend_text TEXT,
    free_weekend_appid INTEGER REFERENCES app (appid),  -- The app a trial runs on, which can be another one
    windows INTEGER,
    mac INTEGER,
    steamos_linux INTEGER,
    steam_deck_compat_category INTEGER,
    steam_os_compat_category INTEGER,
    steam_frame_compat_category INTEGER,
    steam_machine_compat_category INTEGER,
    vr_vrhmd INTEGER,
    vr_vrhmd_only INTEGER,
    vr_htc_vive INTEGER,
    vr_oculus_rift INTEGER,
    vr_windows_mr INTEGER,
    vr_valve_index INTEGER,
    vr_show_optional_vr_mode_notice INTEGER,
    agency INTEGER REFERENCES rating_agency (agency),
    rating TEXT,
    agency_rating INTEGER,
    required_age INTEGER,
    use_age_gate INTEGER,
    banned INTEGER,
    esrb_online_music_not_rated INTEGER,
    esrb_online_interactions_not_rated INTEGER,
    rating_interactive_elements TEXT,
    vetted INTEGER,
    has_community_hub INTEGER,
    points_shop_eligible INTEGER,
    controller_wizard_complete INTEGER,
    item_store_eligible INTEGER,
    item_store_show_featured INTEGER,
    no_mouse_keyboard_support INTEGER,
    refund_checks_ea_playtime INTEGER,
    drm_third_party_type TEXT,
    user_account_third_party TEXT,
    user_account_third_party_link_to_steam INTEGER,
    website TEXT,
    stats_url TEXT,
    online_manual_url TEXT,
    privacy_policy_url TEXT,
    health_warning_url TEXT,
    achievements_visible INTEGER,
    achievement_count INTEGER,
    metacritic_score INTEGER,
    metacritic_url TEXT,
    metacritic_always_show INTEGER,
    anticheat_name TEXT REFERENCES anticheat (name),
    anticheat_kernel_mode INTEGER,
    anticheat_uninstall_completely INTEGER,
    anticheat_boot_protection INTEGER,
    anticheat_boot_protection_name TEXT,
    ai_generation_service_name TEXT,
    ai_generation_service_url TEXT,
    assets_last_modified INTEGER,
    assets_appid INTEGER REFERENCES app (appid),  -- Blank unless its images belong to another app
    FOREIGN KEY (agency, rating) REFERENCES age_rating (agency, rating)
) STRICT;
CREATE TABLE app_text (
    appid INTEGER PRIMARY KEY REFERENCES app (appid),
    short_description TEXT,
    capsule_headline TEXT,
    full_description_bbcode TEXT,
    legal_notice_bbcode TEXT,
    partner_awards_bbcode TEXT,
    content_survey_notes TEXT,
    content_survey_ai_notes TEXT,
    early_access_description_bbcode TEXT,
    early_access_why_bbcode TEXT,
    early_access_how_long_bbcode TEXT,
    early_access_full_version_bbcode TEXT,
    early_access_current_state_bbcode TEXT,
    early_access_pricing_bbcode TEXT,
    early_access_community_bbcode TEXT
) STRICT;

-- What an app is
CREATE TABLE app_category (
    appid INTEGER NOT NULL REFERENCES app (appid),
    categoryid INTEGER NOT NULL REFERENCES store_category (categoryid),
    PRIMARY KEY (appid, categoryid)
) STRICT, WITHOUT ROWID;
CREATE TABLE app_tag (
    appid INTEGER NOT NULL REFERENCES app (appid),
    tagid INTEGER NOT NULL REFERENCES tag (tagid),
    weight INTEGER,
    PRIMARY KEY (appid, tagid)
) STRICT, WITHOUT ROWID;
CREATE TABLE app_genre (
    appid INTEGER NOT NULL REFERENCES app (appid),
    genreid INTEGER NOT NULL REFERENCES genre (genreid),
    position INTEGER NOT NULL,  -- Steam's order, which isn't by id
    PRIMARY KEY (appid, genreid)
) STRICT, WITHOUT ROWID;
CREATE TABLE app_language (
    appid INTEGER NOT NULL REFERENCES app (appid),
    elanguage INTEGER NOT NULL REFERENCES language (elanguage),
    eadditionallanguage INTEGER NOT NULL,
    supported INTEGER,
    full_audio INTEGER,
    subtitles INTEGER,
    PRIMARY KEY (appid, elanguage, eadditionallanguage)
) STRICT, WITHOUT ROWID;
CREATE TABLE app_content_descriptor (
    appid INTEGER NOT NULL REFERENCES app (appid),
    descriptorid INTEGER NOT NULL,
    PRIMARY KEY (appid, descriptorid)
) STRICT, WITHOUT ROWID;
CREATE TABLE app_interactive_element (
    appid INTEGER NOT NULL REFERENCES app (appid),
    element INTEGER NOT NULL,
    PRIMARY KEY (appid, element)
) STRICT, WITHOUT ROWID;
CREATE TABLE app_rating_descriptor (
    appid INTEGER NOT NULL REFERENCES app (appid),
    position INTEGER NOT NULL,
    descriptor TEXT NOT NULL,
    PRIMARY KEY (appid, position)
) STRICT, WITHOUT ROWID;
CREATE TABLE app_document (
    appid INTEGER NOT NULL REFERENCES app (appid),
    document INTEGER NOT NULL,
    PRIMARY KEY (appid, document)
) STRICT, WITHOUT ROWID;
CREATE TABLE app_manufacturer (
    appid INTEGER NOT NULL REFERENCES app (appid),
    position INTEGER NOT NULL,
    name TEXT NOT NULL,
    PRIMARY KEY (appid, position)
) STRICT, WITHOUT ROWID;

-- Who made it. The name shown on an app isn't always the creator's own name, and many credits have no creator id.
CREATE TABLE creator (
    creator_id INTEGER PRIMARY KEY,
    name TEXT,
    store_url_path TEXT,
    store_url_slug TEXT,
    game_count INTEGER
) STRICT;
CREATE TABLE credit (
    credit_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    creator_id INTEGER REFERENCES creator (creator_id),
    UNIQUE (name, creator_id)
) STRICT;
CREATE UNIQUE INDEX credit_without_creator ON credit (name) WHERE creator_id IS NULL;
CREATE TABLE app_credit (
    appid INTEGER NOT NULL REFERENCES app (appid),
    role TEXT NOT NULL CHECK (role IN ('developer', 'publisher', 'franchise')),
    position INTEGER NOT NULL,
    credit_id INTEGER NOT NULL REFERENCES credit (credit_id),
    PRIMARY KEY (appid, role, position)
) STRICT, WITHOUT ROWID;

-- Links between apps
CREATE TABLE app_related (
    appid INTEGER NOT NULL REFERENCES app (appid),
    kind TEXT NOT NULL CHECK (kind IN ('demo', 'standalone_demo', 'playtest', 'dlc_parent', 'included_app', 'related_f2p', 'season_pass')),
    related_appid INTEGER NOT NULL REFERENCES app (appid),
    label TEXT,
    show_above_purchase INTEGER,
    is_open INTEGER,
    header_text TEXT,
    description_text TEXT,
    PRIMARY KEY (appid, kind, related_appid)
) STRICT, WITHOUT ROWID;
CREATE TABLE season_pass_milestone (
    appid INTEGER NOT NULL REFERENCES app (appid),
    milestone_id INTEGER NOT NULL,
    milestone_appid INTEGER REFERENCES app (appid),
    coming_soon_appid INTEGER REFERENCES app (appid),
    event_gid TEXT,
    rtime_complete TEXT,
    shipped INTEGER,
    PRIMARY KEY (appid, milestone_id)
) STRICT, WITHOUT ROWID;
CREATE TABLE season_pass_milestone_date (
    appid INTEGER NOT NULL,
    milestone_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    coming_soon_display_type TEXT,
    rtime TEXT,
    PRIMARY KEY (appid, milestone_id, position),
    FOREIGN KEY (appid, milestone_id) REFERENCES season_pass_milestone (appid, milestone_id)
) STRICT, WITHOUT ROWID;
CREATE TABLE season_pass_milestone_text (
    appid INTEGER NOT NULL,
    milestone_id INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('title', 'description')),
    language INTEGER NOT NULL REFERENCES language (elanguage),
    localized_string TEXT,
    PRIMARY KEY (appid, milestone_id, kind, language),
    FOREIGN KEY (appid, milestone_id) REFERENCES season_pass_milestone (appid, milestone_id)
) STRICT, WITHOUT ROWID;

-- What it costs. A price belongs to the package or bundle, whichever app it's listed under.
CREATE TABLE offer (
    kind TEXT NOT NULL CHECK (kind IN ('package', 'bundle')),
    id INTEGER NOT NULL,
    name TEXT,
    success INTEGER,
    store_url_path TEXT,
    store_url_slug TEXT,  -- Unlike an app's, not always the end of the path
    primary_appid INTEGER REFERENCES app (appid),
    type INTEGER,
    purchase_description_bbcode TEXT,
    unavailable_for_country_restriction INTEGER,
    must_purchase_as_set INTEGER,
    is_free_license INTEGER,
    free_with_master_sub_appid INTEGER REFERENCES app (appid),
    billing_agreement_type INTEGER,
    renewal_time_unit INTEGER,
    renewal_time_period INTEGER,
    renewal_kind TEXT,
    renewal_id INTEGER,
    best_kind TEXT,  -- The cheapest way to buy it, which can be another offer
    best_id INTEGER,
    PRIMARY KEY (kind, id),
    FOREIGN KEY (renewal_kind, renewal_id) REFERENCES offer (kind, id),
    FOREIGN KEY (best_kind, best_id) REFERENCES offer (kind, id)
) STRICT, WITHOUT ROWID;
CREATE TABLE offer_app (  -- By country, because a bundle can hold different games in each store
    kind TEXT NOT NULL,
    id INTEGER NOT NULL,
    country TEXT NOT NULL CHECK (country IN ('BR', 'US')),
    appid INTEGER NOT NULL REFERENCES app (appid),
    PRIMARY KEY (kind, id, country, appid),
    FOREIGN KEY (kind, id) REFERENCES offer (kind, id)
) STRICT, WITHOUT ROWID;
CREATE TABLE offer_category (
    kind TEXT NOT NULL,
    id INTEGER NOT NULL,
    categoryid INTEGER NOT NULL REFERENCES store_category (categoryid),
    PRIMARY KEY (kind, id, categoryid),
    FOREIGN KEY (kind, id) REFERENCES offer (kind, id)
) STRICT, WITHOUT ROWID;
CREATE TABLE offer_content_descriptor (
    kind TEXT NOT NULL,
    id INTEGER NOT NULL,
    descriptorid INTEGER NOT NULL,
    PRIMARY KEY (kind, id, descriptorid),
    FOREIGN KEY (kind, id) REFERENCES offer (kind, id)
) STRICT, WITHOUT ROWID;
CREATE TABLE offer_price (
    kind TEXT NOT NULL,
    id INTEGER NOT NULL,
    country TEXT NOT NULL CHECK (country IN ('BR', 'US')),
    included_game_count INTEGER,
    final_price_in_cents INTEGER,
    original_price_in_cents INTEGER,
    discount_pct INTEGER GENERATED ALWAYS AS (
        CAST(ROUND(100.0 * (original_price_in_cents - final_price_in_cents) / original_price_in_cents) AS INTEGER)
    ) VIRTUAL,
    price_before_bundle_discount INTEGER,
    bundle_discount_pct INTEGER,
    combined_discount_pct INTEGER,
    renewal_price_in_cents INTEGER,
    user_can_purchase_as_gift INTEGER,
    hide_discount_pct_for_compliance INTEGER,
    price_cannot_be_displayed_as_discount INTEGER,
    PRIMARY KEY (kind, id, country),
    FOREIGN KEY (kind, id) REFERENCES offer (kind, id)
) STRICT, WITHOUT ROWID;
CREATE TABLE offer_discount (
    kind TEXT NOT NULL,
    id INTEGER NOT NULL,
    country TEXT NOT NULL,
    position INTEGER NOT NULL,
    discount_amount INTEGER,
    discount_description TEXT,
    discount_end_date TEXT,
    PRIMARY KEY (kind, id, country, position),
    FOREIGN KEY (kind, id, country) REFERENCES offer_price (kind, id, country)
) STRICT, WITHOUT ROWID;
CREATE TABLE app_package_group (
    appid INTEGER NOT NULL REFERENCES app (appid),
    name TEXT NOT NULL,
    display_type INTEGER,
    heading TEXT,
    dropdown_title TEXT,
    dropdown_description_bbcode TEXT,
    PRIMARY KEY (appid, name)
) STRICT, WITHOUT ROWID;
CREATE TABLE app_offer (
    appid INTEGER NOT NULL REFERENCES app (appid),
    kind TEXT NOT NULL,
    id INTEGER NOT NULL,
    package_group TEXT,
    is_edition INTEGER,
    is_best INTEGER NOT NULL,
    PRIMARY KEY (appid, kind, id),
    FOREIGN KEY (kind, id) REFERENCES offer (kind, id),
    FOREIGN KEY (appid, package_group) REFERENCES app_package_group (appid, name)
) STRICT, WITHOUT ROWID;
CREATE UNIQUE INDEX one_best_offer_per_app ON app_offer (appid) WHERE is_best;

-- Media
CREATE TABLE app_asset (
    appid INTEGER NOT NULL REFERENCES app (appid),
    kind TEXT NOT NULL,
    filename TEXT NOT NULL,
    is_override INTEGER NOT NULL,  -- Steam shows this file instead of base_filename, which can be blank
    base_filename TEXT,
    PRIMARY KEY (appid, kind),
    CHECK (is_override OR base_filename IS NULL)
) STRICT, WITHOUT ROWID;
CREATE TABLE app_screenshot (
    appid INTEGER NOT NULL REFERENCES app (appid),
    is_mature INTEGER NOT NULL,
    ordinal INTEGER NOT NULL,
    filename TEXT NOT NULL,
    alt_text TEXT,
    category INTEGER,
    PRIMARY KEY (appid, is_mature, ordinal)
) STRICT, WITHOUT ROWID;
CREATE TABLE trailer (
    trailer_base_id INTEGER PRIMARY KEY,
    trailer_id INTEGER,  -- Not unique: a few ids are two unrelated trailers
    name TEXT,
    url_format TEXT,
    category INTEGER,
    all_ages INTEGER,
    screenshot_small TEXT,
    screenshot_medium TEXT,
    screenshot_full TEXT,
    captions_manifest TEXT
) STRICT;
CREATE TABLE app_trailer (
    appid INTEGER NOT NULL REFERENCES app (appid),
    trailer_base_id INTEGER NOT NULL REFERENCES trailer (trailer_base_id),
    is_highlight INTEGER NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (appid, trailer_base_id)
) STRICT, WITHOUT ROWID;
CREATE TABLE trailer_file (  -- By app too, because apps sharing a trailer can each have their own files
    appid INTEGER NOT NULL,
    trailer_base_id INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('microtrailer', 'adaptive')),
    path TEXT NOT NULL,
    format TEXT NOT NULL,
    PRIMARY KEY (appid, trailer_base_id, kind, path, format),
    FOREIGN KEY (appid, trailer_base_id) REFERENCES app_trailer (appid, trailer_base_id)
) STRICT, WITHOUT ROWID;

-- Other store lists
CREATE TABLE app_link (
    appid INTEGER NOT NULL REFERENCES app (appid),
    position INTEGER NOT NULL,
    link_type INTEGER,
    url TEXT,
    link_text TEXT,
    PRIMARY KEY (appid, position)
) STRICT, WITHOUT ROWID;
CREATE TABLE app_eula (
    appid INTEGER NOT NULL REFERENCES app (appid),
    position INTEGER NOT NULL,
    name TEXT,
    url TEXT,
    PRIMARY KEY (appid, position)
) STRICT, WITHOUT ROWID;
CREATE TABLE app_press_review (
    appid INTEGER NOT NULL REFERENCES app (appid),
    position INTEGER NOT NULL,
    quote TEXT,
    score TEXT,
    site TEXT,
    url TEXT,
    PRIMARY KEY (appid, position)
) STRICT, WITHOUT ROWID;
CREATE TABLE app_section (
    appid INTEGER NOT NULL REFERENCES app (appid),
    position INTEGER NOT NULL,
    label TEXT,
    banner INTEGER,
    content_bbcode TEXT,
    PRIMARY KEY (appid, position)
) STRICT, WITHOUT ROWID;
CREATE TABLE app_sale_page (
    appid INTEGER NOT NULL REFERENCES app (appid),
    position INTEGER NOT NULL,
    clan_account_id INTEGER,
    event_gid TEXT,
    PRIMARY KEY (appid, position)
) STRICT, WITHOUT ROWID;
CREATE TABLE app_steam_award (
    appid INTEGER NOT NULL REFERENCES app (appid),
    position INTEGER NOT NULL,
    voteid INTEGER,
    award_year INTEGER,
    title TEXT,
    PRIMARY KEY (appid, position)
) STRICT, WITHOUT ROWID;
CREATE TABLE app_purchase_note (
    appid INTEGER NOT NULL REFERENCES app (appid),
    position INTEGER NOT NULL,
    type INTEGER,
    highlighted INTEGER,
    text_bbcode TEXT,
    PRIMARY KEY (appid, position)
) STRICT, WITHOUT ROWID;
CREATE TABLE app_optin_tag (
    appid INTEGER NOT NULL REFERENCES app (appid),
    optin_name TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (appid, optin_name, value)
) STRICT, WITHOUT ROWID;

-- System requirements
CREATE TABLE app_platform_requirement (
    appid INTEGER NOT NULL REFERENCES app (appid),
    platform INTEGER NOT NULL,
    requires_64bit INTEGER,
    requires_apple_silicon INTEGER,
    unsupported_os_note INTEGER,
    PRIMARY KEY (appid, platform)
) STRICT, WITHOUT ROWID;
CREATE TABLE app_system_requirement (
    appid INTEGER NOT NULL,
    platform INTEGER NOT NULL,
    tier TEXT NOT NULL CHECK (tier IN ('minimum', 'recommended')),
    os_version TEXT,
    os_version_unsupported INTEGER,
    processor TEXT,
    memory_amount TEXT,
    memory_units TEXT,
    graphics TEXT,
    directx TEXT,
    storage_amount TEXT,
    storage_units TEXT,
    storage_hq_amount TEXT,
    storage_hq_units TEXT,
    sound_card TEXT,
    notes TEXT,
    legacy_bbcode TEXT,
    broadband INTEGER,
    vr_support TEXT,
    PRIMARY KEY (appid, platform, tier),
    FOREIGN KEY (appid, platform) REFERENCES app_platform_requirement (appid, platform)
) STRICT, WITHOUT ROWID;

-- Reviews
CREATE TABLE app_review_summary (
    appid INTEGER NOT NULL REFERENCES app (appid),
    scope TEXT NOT NULL CHECK (scope IN ('filtered', 'language', 'unfiltered')),
    review_count INTEGER,
    percent_positive INTEGER,  -- Truncated, not rounded
    review_score INTEGER REFERENCES review_score (review_score),
    PRIMARY KEY (appid, scope)
) STRICT, WITHOUT ROWID;
CREATE TABLE app_review_total (  -- Worked out by steam-games, whose catalog is the only one with these
    appid INTEGER PRIMARY KEY REFERENCES app (appid),
    positive INTEGER NOT NULL,
    negative INTEGER NOT NULL,
    counts_exact INTEGER NOT NULL  -- 0: midpoint estimate from percent_positive
) STRICT;
CREATE TABLE app_review_histogram (  -- A separate figure from review_count, usually higher, so don't divide one by the other
    appid INTEGER PRIMARY KEY REFERENCES app (appid),
    rollup_type TEXT,
    start_date TEXT,
    end_date TEXT
) STRICT;
CREATE TABLE review_history (
    appid INTEGER NOT NULL REFERENCES app_review_histogram (appid),
    is_recent INTEGER NOT NULL,  -- 1: the daily counts of the last few weeks, which also count towards the rollups
    date TEXT NOT NULL,
    recommendations_up INTEGER,
    recommendations_down INTEGER,
    PRIMARY KEY (appid, is_recent, date)
) STRICT, WITHOUT ROWID;

-- My account
CREATE TABLE wishlist_item (
    appid INTEGER PRIMARY KEY REFERENCES app (appid),
    position INTEGER NOT NULL UNIQUE,  -- Order of the API's answer
    priority INTEGER,  -- Blank: unranked
    date_added TEXT
) STRICT;
CREATE TABLE wishlist_category (categoryid INTEGER PRIMARY KEY, name TEXT, notification_opt_in INTEGER) STRICT;
CREATE TABLE wishlist_item_category (
    appid INTEGER NOT NULL REFERENCES wishlist_item (appid),
    categoryid INTEGER NOT NULL REFERENCES wishlist_category (categoryid),
    PRIMARY KEY (appid, categoryid)
) STRICT, WITHOUT ROWID;
CREATE TABLE owned_game (
    appid INTEGER PRIMARY KEY REFERENCES app (appid),
    library_name TEXT,  -- Often differs from the store's name, and the store has none for some delisted apps
    sort_as TEXT,
    img_icon_url TEXT,
    capsule_filename TEXT,
    has_workshop INTEGER,
    has_market INTEGER,
    has_dlc INTEGER,
    has_community_visible_stats INTEGER,
    has_leaderboards INTEGER,
    family_shared INTEGER
) STRICT;
CREATE TABLE playtime (  -- In minutes. Only played apps have a row, and not all of them are owned.
    appid INTEGER PRIMARY KEY REFERENCES app (appid),
    playtime_forever INTEGER,
    playtime_2weeks INTEGER,
    playtime_windows_forever INTEGER,
    playtime_mac_forever INTEGER,
    playtime_linux_forever INTEGER,
    playtime_deck_forever INTEGER,
    playtime_disconnected INTEGER,
    first_playtime TEXT,
    first_windows_playtime TEXT,
    first_mac_playtime TEXT,
    first_linux_playtime TEXT,
    first_deck_playtime TEXT,
    last_playtime TEXT,
    last_windows_playtime TEXT,
    last_mac_playtime TEXT,
    last_linux_playtime TEXT,
    last_deck_playtime TEXT
) STRICT;
CREATE TABLE achievement_progress (
    appid INTEGER PRIMARY KEY REFERENCES app (appid),
    unlocked INTEGER,
    total INTEGER,
    cache_time TEXT,
    vetted INTEGER,
    groups_completed_base INTEGER,
    groups_total_base INTEGER,
    groups_completed_dlc INTEGER,
    groups_total_dlc INTEGER,
    base_game_total INTEGER
) STRICT;
CREATE TABLE game_note (
    note_id TEXT PRIMARY KEY,
    appid INTEGER REFERENCES app (appid),  -- Blank for a non-Steam shortcut
    shortcut_name TEXT,
    shortcutid INTEGER,
    ordinal INTEGER,
    title TEXT,
    content TEXT,
    time_created TEXT,
    time_modified TEXT
) STRICT, WITHOUT ROWID;
CREATE TABLE private_app (appid INTEGER PRIMARY KEY REFERENCES app (appid)) STRICT;
CREATE TABLE followed_app (appid INTEGER PRIMARY KEY REFERENCES app (appid)) STRICT;
CREATE TABLE ignored_app (appid INTEGER PRIMARY KEY REFERENCES app (appid), reason TEXT) STRICT;
CREATE TABLE list_entry (appid INTEGER PRIMARY KEY REFERENCES app (appid), status TEXT, on_notion INTEGER) STRICT;

CREATE VIEW v_achievement_status AS
SELECT
    appid,
    unlocked,
    total,
    IIF(total > 0, 100.0 * unlocked / total, 0.0) AS percentage,
    total > 0 AND unlocked = total AS all_unlocked
FROM achievement_progress;

CREATE VIEW v_wishlist_category_size AS
SELECT c.categoryid, COUNT(m.appid) AS item_count
FROM wishlist_category AS c
LEFT JOIN wishlist_item_category AS m USING (categoryid)
GROUP BY c.categoryid;
