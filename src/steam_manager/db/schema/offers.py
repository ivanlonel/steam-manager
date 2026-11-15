"""
The tables of what an app costs.

A price belongs to a package or bundle, an **offer**, whichever app it is listed under, and is
kept under the country it was quoted in.
"""

from sqlalchemy import CheckConstraint, Computed, ForeignKey, ForeignKeyConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from steam_manager.db.schema.apps import App
from steam_manager.db.schema.base import STRICT_WITHOUT_ROWID, SteamBase
from steam_manager.db.schema.lookups import StoreCategory


class Offer(SteamBase):
    """A package or bundle."""

    __tablename__ = "offer"
    __table_args__ = (
        CheckConstraint("kind IN ('package', 'bundle')"),
        ForeignKeyConstraint(["renewal_kind", "renewal_id"], ["offer.kind", "offer.id"]),
        ForeignKeyConstraint(["best_kind", "best_id"], ["offer.kind", "offer.id"]),
        STRICT_WITHOUT_ROWID,
    )

    kind: Mapped[str] = mapped_column(primary_key=True)
    """``package`` or ``bundle``."""
    id: Mapped[int] = mapped_column(primary_key=True)
    """Steam's id for it, unique within its kind."""
    name: Mapped[str | None]
    """Its name."""
    success: Mapped[int | None]
    """Steam's result code; 1 is success."""
    store_url_path: Mapped[str | None]
    """Its store page."""
    store_url_slug: Mapped[str | None]
    """The slug of that page, which unlike an app's isn't always the end of the path."""
    primary_appid: Mapped[int | None] = mapped_column(ForeignKey(App.appid))
    """The app it is tied to."""
    type: Mapped[int | None]
    """Steam's code for its kind."""
    purchase_description_bbcode: Mapped[str | None]
    """Its description next to the buy button, in BBCode."""
    unavailable_for_country_restriction: Mapped[bool | None]
    """Whether the country can't buy it."""
    must_purchase_as_set: Mapped[bool | None]
    """Whether a bundle can only be bought whole."""
    is_free_license: Mapped[bool | None]
    """Whether it is a free license."""
    free_with_master_sub_appid: Mapped[int | None] = mapped_column(ForeignKey(App.appid))
    """The subscription app that gives it for free."""
    billing_agreement_type: Mapped[int | None]
    """Steam's code for a subscription's kind of agreement."""
    renewal_time_unit: Mapped[int | None]
    """Steam's code for the unit of the renewal period."""
    renewal_time_period: Mapped[int | None]
    """How many units the renewal period lasts."""
    renewal_kind: Mapped[str | None]
    """The kind of the offer that renews it."""
    renewal_id: Mapped[int | None]
    """That offer's id."""
    best_kind: Mapped[str | None]
    """The kind of the cheapest way to buy it, which can be another offer."""
    best_id: Mapped[int | None]
    """That offer's id."""


class OfferApp(SteamBase):
    """An app an offer holds, per country, since a bundle can hold different apps in each store."""

    __tablename__ = "offer_app"
    __table_args__ = (
        ForeignKeyConstraint(["kind", "id"], [Offer.kind, Offer.id]),
        STRICT_WITHOUT_ROWID,
    )

    kind: Mapped[str] = mapped_column(primary_key=True)
    """The offer's kind."""
    id: Mapped[int] = mapped_column(primary_key=True)
    """The offer's id."""
    country: Mapped[str] = mapped_column(primary_key=True)
    """The store country that listed it."""
    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""


class OfferCategory(SteamBase):
    """A store category an offer is in."""

    __tablename__ = "offer_category"
    __table_args__ = (
        ForeignKeyConstraint(["kind", "id"], [Offer.kind, Offer.id]),
        STRICT_WITHOUT_ROWID,
    )

    kind: Mapped[str] = mapped_column(primary_key=True)
    """The offer's kind."""
    id: Mapped[int] = mapped_column(primary_key=True)
    """The offer's id."""
    categoryid: Mapped[int] = mapped_column(ForeignKey(StoreCategory.categoryid), primary_key=True)
    """The category."""


class OfferContentDescriptor(SteamBase):
    """A content descriptor an offer carries, such as violence."""

    __tablename__ = "offer_content_descriptor"
    __table_args__ = (
        ForeignKeyConstraint(["kind", "id"], [Offer.kind, Offer.id]),
        STRICT_WITHOUT_ROWID,
    )

    kind: Mapped[str] = mapped_column(primary_key=True)
    """The offer's kind."""
    id: Mapped[int] = mapped_column(primary_key=True)
    """The offer's id."""
    descriptorid: Mapped[int] = mapped_column(primary_key=True)
    """Steam's code for the descriptor."""


class OfferPrice(SteamBase):
    """What an offer costs in one country, in that country's currency."""

    __tablename__ = "offer_price"
    __table_args__ = (
        ForeignKeyConstraint(["kind", "id"], [Offer.kind, Offer.id]),
        STRICT_WITHOUT_ROWID,
    )

    kind: Mapped[str] = mapped_column(primary_key=True)
    """The offer's kind."""
    id: Mapped[int] = mapped_column(primary_key=True)
    """The offer's id."""
    country: Mapped[str] = mapped_column(primary_key=True)
    """The store country that quoted it."""
    included_game_count: Mapped[int | None]
    """How many games it holds."""
    final_price_in_cents: Mapped[int | None]
    """What it costs now, in cents."""
    original_price_in_cents: Mapped[int | None]
    """What it costs without a discount, in cents."""
    discount_pct: Mapped[int | None] = mapped_column(
        Computed(
            "CAST(ROUND(100.0 * (original_price_in_cents - final_price_in_cents)"
            " / original_price_in_cents) AS INTEGER)",
            persisted=False,
        )
    )
    """The discount on the original price, in percent, worked out from the two prices."""
    price_before_bundle_discount: Mapped[int | None]
    """What a bundle's parts cost bought apart, in cents."""
    bundle_discount_pct: Mapped[int | None]
    """The bundle's discount on its parts, in percent."""
    combined_discount_pct: Mapped[int | None]
    """Both discounts together, in percent."""
    renewal_price_in_cents: Mapped[int | None]
    """What each renewal of a subscription costs, in cents."""
    user_can_purchase_as_gift: Mapped[bool | None]
    """Whether it can be bought as a gift."""
    hide_discount_pct_for_compliance: Mapped[bool | None]
    """Whether the store hides the discount, as some countries' rules require."""
    price_cannot_be_displayed_as_discount: Mapped[bool | None]
    """Whether the store may not show the price as a discount."""
    formatted_final_price: Mapped[str | None]
    """The final price as the store shows it, which the notebook worked out instead."""
    formatted_original_price: Mapped[str | None]
    """The original price as the store shows it."""
    formatted_price_before_bundle_discount: Mapped[str | None]
    """The parts' price as the store shows it."""
    formatted_renewal_price: Mapped[str | None]
    """The renewal price as the store shows it."""


class OfferDiscount(SteamBase):
    """A discount running on an offer in one country."""

    __tablename__ = "offer_discount"
    __table_args__ = (
        ForeignKeyConstraint(
            ["kind", "id", "country"], [OfferPrice.kind, OfferPrice.id, OfferPrice.country]
        ),
        STRICT_WITHOUT_ROWID,
    )

    kind: Mapped[str] = mapped_column(primary_key=True)
    """The offer's kind."""
    id: Mapped[int] = mapped_column(primary_key=True)
    """The offer's id."""
    country: Mapped[str] = mapped_column(primary_key=True)
    """The country of the price it applies to."""
    position: Mapped[int] = mapped_column(primary_key=True)
    """Its place in Steam's list."""
    discount_amount: Mapped[int | None]
    """How much it takes off, in cents."""
    discount_description: Mapped[str | None]
    """Its name, as the store shows it."""
    discount_end_date: Mapped[str | None]
    """When it ends."""


class AppPackageGroup(SteamBase):
    """A group of buy options on an app's store page."""

    __tablename__ = "app_package_group"
    __table_args__ = STRICT_WITHOUT_ROWID

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    name: Mapped[str] = mapped_column(primary_key=True)
    """The group's name."""
    display_type: Mapped[int | None]
    """Steam's code for how it is shown."""
    heading: Mapped[str | None]
    """Its heading."""
    dropdown_title: Mapped[str | None]
    """The title of its drop-down."""
    dropdown_description_bbcode: Mapped[str | None]
    """The description of its drop-down, in BBCode."""


class AppOffer(SteamBase):
    """An offer listed under an app, one of which is the cheapest way to buy it."""

    __tablename__ = "app_offer"
    __table_args__ = (
        ForeignKeyConstraint(["kind", "id"], [Offer.kind, Offer.id]),
        ForeignKeyConstraint(
            ["appid", "package_group"], [AppPackageGroup.appid, AppPackageGroup.name]
        ),
        Index("one_best_offer_per_app", "appid", unique=True, sqlite_where=text("is_best")),
        STRICT_WITHOUT_ROWID,
    )

    appid: Mapped[int] = mapped_column(ForeignKey(App.appid), primary_key=True)
    """The app."""
    kind: Mapped[str] = mapped_column(primary_key=True)
    """The offer's kind."""
    id: Mapped[int] = mapped_column(primary_key=True)
    """The offer's id."""
    package_group: Mapped[str | None]
    """The group of the store page it is shown in."""
    is_edition: Mapped[bool | None]
    """Whether the store shows it as an edition of the app."""
    is_best: Mapped[bool]
    """Whether it is the cheapest way to buy the app."""
