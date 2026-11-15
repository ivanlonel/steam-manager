"""Payload models of the ways to buy an app: packages and bundles, with their prices."""

from steam_manager.steam.models.base import SteamModel


class ActiveDiscount(SteamModel):
    """A discount running on an offer."""

    discount_amount: int | None = None
    """How much it takes off, in cents."""
    discount_description: str | None = None
    """Its name, as the store shows it."""
    discount_end_date: int | None = None
    """When it ends, in epoch seconds."""


class RecurrenceInfo(SteamModel):
    """How a subscription offer renews."""

    packageid: int | None = None
    """The package that renews."""
    billing_agreement_type: int | None = None
    """Steam's code for the kind of agreement."""
    renewal_time_unit: int | None = None
    """Steam's code for the unit of the renewal period."""
    renewal_time_period: int | None = None
    """How many units the renewal period lasts."""
    renewal_price_in_cents: int | None = None
    """What each renewal costs, in cents."""
    formatted_renewal_price: str | None = None
    """That price as the store shows it."""


class PurchaseOption(SteamModel):
    """A package or bundle an app can be bought through, priced in the country asked."""

    packageid: int | None = None
    """The package's id, when the offer is a package."""
    bundleid: int | None = None
    """The bundle's id, when the offer is a bundle."""
    purchase_option_name: str | None = None
    """The offer's name on the store page."""
    package_group: str | None = None
    """The group of the store page it is shown in."""
    is_edition: bool | None = None
    """Whether the store shows it as an edition of the app."""
    must_purchase_as_set: bool | None = None
    """Whether a bundle can only be bought whole."""
    included_game_count: int | None = None
    """How many games it holds."""
    is_free_license: bool | None = None
    """Whether it is a free license."""
    free_with_master_sub_appid: int | None = None
    """The subscription app that gives it for free."""
    final_price_in_cents: int | None = None
    """What it costs now, in cents."""
    original_price_in_cents: int | None = None
    """What it costs without a discount, in cents."""
    price_before_bundle_discount: int | None = None
    """What a bundle's parts cost bought apart, in cents."""
    discount_pct: int | None = None
    """The discount on the original price, in percent."""
    bundle_discount_pct: int | None = None
    """The bundle's discount on its parts, in percent."""
    combined_discount_pct: int | None = None
    """Both discounts together, in percent."""
    formatted_final_price: str | None = None
    """The final price as the store shows it."""
    formatted_original_price: str | None = None
    """The original price as the store shows it."""
    formatted_price_before_bundle_discount: str | None = None
    """The parts' price as the store shows it."""
    user_can_purchase_as_gift: bool | None = None
    """Whether it can be bought as a gift."""
    hide_discount_pct_for_compliance: bool | None = None
    """Whether the store hides the discount, as some countries' rules require."""
    price_cannot_be_displayed_as_discount: bool | None = None
    """Whether the store may not show the price as a discount."""
    active_discounts: tuple[ActiveDiscount, ...] = ()
    """The discounts running on it."""
    recurrence_info: RecurrenceInfo | None = None
    """How it renews, for a subscription."""
