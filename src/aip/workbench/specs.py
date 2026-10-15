"""Workbench dataset specifications: eight synthetic data types with planted structure.

Each dataset has K hidden segments. Features draw from segment-specific distributions, so a seed list
drawn mostly from some segments has real structure for look-alike modeling to find, a behavioral pattern
exists for act-alike modeling, and (where a label exists) an outcome follows a known logistic link.
Nothing here describes a real population; the numbers are chosen to make method differences visible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

FeatureKind = Literal["count", "share", "binary", "score"]
Family = Literal["behavioral", "declared", "provider_inferred", "contextual", "aggregate"]
Method = Literal["lookalike", "actalike", "propensity", "byom", "semantic"]


@dataclass(frozen=True)
class Feature:
    name: str
    label: str
    kind: FeatureKind
    family: Family
    means: tuple[float, ...]  # one per segment: count -> Poisson mean, share/binary -> probability, score -> mean
    missing: float = 0.0
    sensitive: bool = False


@dataclass(frozen=True)
class Unit:
    type_id: str
    namespace: str
    key_field: str
    id_prefix: str
    label: str


@dataclass(frozen=True)
class Outcome:
    event: str
    label: str
    horizon_days: int
    weights: dict[str, float]  # standardized-feature weights of the true logistic link
    base_rate: float


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    title: str
    type_label: str
    summary: str
    unit: Unit
    n: int
    segment_probs: tuple[float, ...]
    segment_labels: tuple[str, ...]
    features: tuple[Feature, ...]
    breakdown_label: str
    breakdown_values: tuple[str, ...]
    breakdown_by_segment: tuple[tuple[float, ...], ...]  # per segment, probabilities over breakdown_values
    collection_method: str
    location: Literal["workspace", "cleanroom"]
    methods: tuple[Method, ...]
    seed_label: str | None = None
    seed_size: int = 0
    seed_segment_weights: tuple[float, ...] = ()
    behavior_label: str | None = None
    behavior_features: tuple[str, ...] = ()
    behavior_share: float = 0.0
    outcome: Outcome | None = None
    brief_label: str | None = None
    brief_segment: int | None = None
    known_limits: tuple[str, ...] = field(default=())
    rng_seed: int = 20261015


K5 = (0.22, 0.18, 0.2, 0.25, 0.15)

DATASETS: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        dataset_id="b2b_accounts",
        title="B2B accounts",
        type_label="B2B",
        summary=(
            "Companies with firmographics, technology signals and "
            "research intent. Find accounts like your best customers."
        ),
        unit=Unit("business_account", "wb_b2b_account", "account_id", "acct_", "Business account"),
        n=8000,
        segment_probs=K5,
        segment_labels=("Enterprise SaaS", "Mid-market services", "SMB retail", "Manufacturing", "Public sector"),
        features=(
            Feature("employees_log", "Employees (log scale)", "score", "declared", (8.0, 6.0, 3.5, 6.5, 7.0)),
            Feature("revenue_index", "Revenue index", "score", "declared", (9.0, 6.5, 3.0, 7.0, 5.5)),
            Feature(
                "cloud_stack",
                "Runs a public-cloud stack",
                "binary",
                "provider_inferred",
                (0.9, 0.6, 0.3, 0.4, 0.35),
                0.1,
            ),
            Feature(
                "crm_installed", "Has a CRM installed", "binary", "provider_inferred", (0.95, 0.8, 0.4, 0.5, 0.6), 0.1
            ),
            Feature("intent_adtech", "Research intent: ad tech", "score", "behavioral", (6.0, 3.5, 1.5, 1.0, 1.2), 0.2),
            Feature(
                "intent_data", "Research intent: data platforms", "score", "behavioral", (5.5, 4.0, 1.0, 2.0, 2.5), 0.2
            ),
            Feature("site_visits_30d", "Site visits, 30 days", "count", "behavioral", (6.0, 3.0, 1.0, 1.5, 1.0)),
            Feature(
                "hiring_growth", "Hiring growth index", "score", "provider_inferred", (2.0, 1.0, 0.0, 0.5, -0.5), 0.15
            ),
        ),
        breakdown_label="Industry",
        breakdown_values=("Software", "Services", "Retail", "Manufacturing", "Government"),
        breakdown_by_segment=(
            (0.8, 0.1, 0.05, 0.05, 0.0),
            (0.15, 0.7, 0.1, 0.05, 0.0),
            (0.05, 0.1, 0.8, 0.05, 0.0),
            (0.05, 0.05, 0.05, 0.85, 0.0),
            (0.05, 0.1, 0.0, 0.05, 0.8),
        ),
        collection_method="vendor_model",
        location="workspace",
        methods=("lookalike", "actalike", "propensity"),
        seed_label="Closed-won customers",
        seed_size=240,
        seed_segment_weights=(0.6, 0.3, 0.02, 0.06, 0.02),
        behavior_label="Accounts researching ad tech and data platforms",
        behavior_features=("intent_adtech", "intent_data", "site_visits_30d"),
        behavior_share=0.06,
        outcome=Outcome(
            "opportunity_created",
            "opportunity created",
            90,
            {"intent_adtech": 1.2, "site_visits_30d": 0.8, "employees_log": 0.4},
            0.006,
        ),
        known_limits=(
            "Firmographics are provider-declared and lag real changes",
            "Intent is topic research, not purchase intent",
        ),
        rng_seed=20261101,
    ),
    DatasetSpec(
        dataset_id="geo_areas",
        title="Geography",
        type_label="GEO",
        summary=(
            "Postal areas with population, income and "
            "category-spend indices. Find areas like your best-performing ones."
        ),
        unit=Unit("postal_code", "wb_us_zip5", "zip5", "", "Postal area"),
        n=6000,
        segment_probs=(0.25, 0.25, 0.2, 0.15, 0.15),
        segment_labels=("Urban core", "Inner suburbs", "Outer suburbs", "Small towns", "Rural"),
        features=(
            Feature("density_index", "Population density index", "score", "aggregate", (9.0, 6.0, 4.0, 2.5, 1.0)),
            Feature("income_index", "Median income index", "score", "aggregate", (6.0, 7.5, 6.5, 4.5, 4.0)),
            Feature("share_25_44", "Share aged 25 to 44", "share", "aggregate", (0.42, 0.33, 0.28, 0.24, 0.2)),
            Feature("share_families", "Share of family households", "share", "aggregate", (0.3, 0.55, 0.62, 0.5, 0.48)),
            Feature("spend_outdoor", "Outdoor category spend index", "score", "aggregate", (3.0, 4.5, 6.0, 5.5, 7.0)),
            Feature("spend_dining", "Dining spend index", "score", "aggregate", (8.0, 6.0, 4.5, 3.5, 2.5)),
            Feature("store_km", "Distance to nearest store (km)", "score", "aggregate", (2.0, 5.0, 9.0, 15.0, 30.0)),
        ),
        breakdown_label="Region",
        breakdown_values=("Northeast", "Midwest", "South", "West"),
        breakdown_by_segment=(
            (0.35, 0.2, 0.2, 0.25),
            (0.25, 0.25, 0.3, 0.2),
            (0.2, 0.3, 0.3, 0.2),
            (0.15, 0.35, 0.35, 0.15),
            (0.1, 0.35, 0.35, 0.2),
        ),
        collection_method="other",
        location="workspace",
        methods=("lookalike",),
        seed_label="Top-performing postal areas for a store opening",
        seed_size=150,
        seed_segment_weights=(0.05, 0.55, 0.35, 0.05, 0.0),
        known_limits=("Area context only; never a personal trait", "Indices are synthetic and relative to this file"),
        rng_seed=20261102,
    ),
    DatasetSpec(
        dataset_id="demo_firmo",
        title="Demographic and firmographic",
        type_label="Demographic and firmographic",
        summary=(
            "People with declared demographics and their employer's "
            "firmographics. One column is sensitive and is excluded before any modeling."
        ),
        unit=Unit("person_key", "wb_provider_person", "person_id", "p_", "Person"),
        n=20000,
        segment_probs=K5,
        segment_labels=("Early-career tech", "Senior decision makers", "Family households", "Retirees", "Students"),
        features=(
            Feature("age_band_index", "Age band (index)", "score", "declared", (3.0, 5.0, 4.0, 7.0, 1.5)),
            Feature("household_size", "Household size", "count", "declared", (1.5, 2.5, 4.0, 2.0, 1.2)),
            Feature("income_band_index", "Income band (index)", "score", "declared", (5.0, 8.0, 5.5, 4.0, 1.5), 0.15),
            Feature("seniority_index", "Job seniority (index)", "score", "declared", (2.5, 7.5, 4.0, 0.5, 0.2), 0.25),
            Feature("company_size_index", "Employer size (index)", "score", "declared", (6.5, 7.0, 4.5, 0.5, 0.5), 0.3),
            Feature(
                "tech_function", "Works in a technical function", "binary", "declared", (0.8, 0.4, 0.2, 0.05, 0.1), 0.25
            ),
            Feature(
                "health_condition_inferred",
                "Inferred health condition",
                "binary",
                "provider_inferred",
                (0.1, 0.15, 0.2, 0.45, 0.05),
                0.2,
                sensitive=True,
            ),
        ),
        breakdown_label="Age group",
        breakdown_values=("18-24", "25-34", "35-54", "55+"),
        breakdown_by_segment=(
            (0.15, 0.7, 0.15, 0.0),
            (0.0, 0.2, 0.7, 0.1),
            (0.0, 0.3, 0.65, 0.05),
            (0.0, 0.0, 0.15, 0.85),
            (0.9, 0.1, 0.0, 0.0),
        ),
        collection_method="survey_response",
        location="workspace",
        methods=("lookalike",),
        seed_label="Webinar registrants",
        seed_size=400,
        seed_segment_weights=(0.45, 0.45, 0.05, 0.0, 0.05),
        known_limits=("Declared attributes can be stale", "Sensitive attributes are excluded from every model"),
        rng_seed=20261103,
    ),
    DatasetSpec(
        dataset_id="interest_segments",
        title="Interest and behavioral segments",
        type_label="Interest and behavioral segments",
        summary="Mobile devices with provider interest segments and app behavior. Model on seeds, or on behavior.",
        unit=Unit("mobile_ad_id", "wb_maid", "maid", "maid_", "Mobile device"),
        n=20000,
        segment_probs=K5,
        segment_labels=("Sports fans", "Travelers", "Gamers", "Home and garden", "Finance watchers"),
        features=(
            Feature(
                "seg_sports", "Interest segment: sports", "binary", "provider_inferred", (0.85, 0.2, 0.3, 0.15, 0.2)
            ),
            Feature(
                "seg_travel", "Interest segment: travel", "binary", "provider_inferred", (0.2, 0.85, 0.1, 0.2, 0.3)
            ),
            Feature(
                "seg_gaming", "Interest segment: gaming", "binary", "provider_inferred", (0.3, 0.1, 0.9, 0.05, 0.1)
            ),
            Feature(
                "seg_home",
                "Interest segment: home and garden",
                "binary",
                "provider_inferred",
                (0.1, 0.2, 0.05, 0.85, 0.2),
            ),
            Feature(
                "seg_finance", "Interest segment: finance", "binary", "provider_inferred", (0.15, 0.3, 0.05, 0.25, 0.85)
            ),
            Feature("app_sessions_7d", "App sessions, 7 days", "count", "behavioral", (12.0, 6.0, 25.0, 5.0, 8.0), 0.1),
            Feature(
                "purchase_in_app_30d",
                "In-app purchases, 30 days",
                "count",
                "behavioral",
                (0.6, 0.4, 2.5, 0.3, 0.2),
                0.1,
            ),
            Feature(
                "video_minutes_7d", "Video minutes, 7 days", "count", "behavioral", (90.0, 40.0, 60.0, 25.0, 20.0), 0.1
            ),
        ),
        breakdown_label="Platform",
        breakdown_values=("iOS", "Android"),
        breakdown_by_segment=((0.45, 0.55), (0.6, 0.4), (0.4, 0.6), (0.5, 0.5), (0.65, 0.35)),
        collection_method="sdk",
        location="workspace",
        methods=("lookalike", "actalike"),
        seed_label="Installers of a fantasy-sports app",
        seed_size=500,
        seed_segment_weights=(0.7, 0.05, 0.2, 0.0, 0.05),
        behavior_label="Heavy in-app spenders",
        behavior_features=("app_sessions_7d", "purchase_in_app_30d"),
        behavior_share=0.05,
        known_limits=(
            "Interest segments are provider-inferred, not observed",
            "Device IDs reset; counts are device-level",
        ),
        rng_seed=20261104,
    ),
    DatasetSpec(
        dataset_id="acr_tv",
        title="TV viewing (ACR)",
        type_label="TV viewing (ACR)",
        summary=(
            "Households with viewing minutes by genre and daypart, held "
            "in a clean room. Models run inside; only aggregates leave."
        ),
        unit=Unit("provider_household_key", "acr_demo_hh", "household_id", "hh_", "Household"),
        n=15000,
        segment_probs=K5,
        segment_labels=("Sports-heavy", "News-heavy", "Kids and family", "Streaming-first", "Light viewers"),
        features=(
            Feature("min_sports_7d", "Sports minutes, 7 days", "count", "behavioral", (420.0, 60.0, 50.0, 80.0, 20.0)),
            Feature("min_news_7d", "News minutes, 7 days", "count", "behavioral", (90.0, 480.0, 40.0, 50.0, 30.0)),
            Feature("min_kids_7d", "Kids minutes, 7 days", "count", "behavioral", (40.0, 20.0, 400.0, 60.0, 15.0)),
            Feature(
                "min_streaming_7d",
                "Streaming-app minutes, 7 days",
                "count",
                "behavioral",
                (120.0, 60.0, 180.0, 600.0, 40.0),
            ),
            Feature(
                "share_primetime", "Share of viewing in prime time", "share", "behavioral", (0.45, 0.35, 0.3, 0.5, 0.4)
            ),
            Feature(
                "share_weekend", "Share of viewing at weekends", "share", "behavioral", (0.5, 0.25, 0.4, 0.35, 0.3)
            ),
        ),
        breakdown_label="Daypart skew",
        breakdown_values=("Morning", "Daytime", "Prime time", "Late night"),
        breakdown_by_segment=(
            (0.1, 0.2, 0.55, 0.15),
            (0.4, 0.3, 0.25, 0.05),
            (0.35, 0.4, 0.2, 0.05),
            (0.05, 0.15, 0.45, 0.35),
            (0.25, 0.3, 0.35, 0.1),
        ),
        collection_method="fingerprint_match",
        location="cleanroom",
        methods=("lookalike", "actalike"),
        seed_label="Brand customers matched in the clean room",
        seed_size=450,
        seed_segment_weights=(0.6, 0.05, 0.05, 0.3, 0.0),
        behavior_label="Live-sports viewers in the last week",
        behavior_features=("min_sports_7d", "share_weekend"),
        behavior_share=0.08,
        known_limits=("Only smart TVs with ACR consent are observed", "Row-level outputs never leave the clean room"),
        rng_seed=20261105,
    ),
    DatasetSpec(
        dataset_id="web_app",
        title="Web and app events",
        type_label="Web and app events",
        summary="Browsers with sessions, category views, cart adds and conversions. All three model types apply.",
        unit=Unit("browser_cookie", "wb_web_cookie", "cookie_id", "ck_", "Browser"),
        n=20000,
        segment_probs=K5,
        segment_labels=("Deal hunters", "Loyal shoppers", "Browsers", "Researchers", "One-time visitors"),
        features=(
            Feature("sessions_28d", "Sessions, 28 days", "count", "behavioral", (8.0, 14.0, 5.0, 10.0, 1.2)),
            Feature("views_apparel", "Apparel product views", "count", "behavioral", (12.0, 18.0, 6.0, 4.0, 1.0), 0.05),
            Feature("views_home", "Home product views", "count", "behavioral", (4.0, 10.0, 3.0, 12.0, 0.5), 0.05),
            Feature("cart_adds_28d", "Cart adds, 28 days", "count", "behavioral", (3.0, 4.0, 0.6, 1.0, 0.1)),
            Feature("coupon_clicks", "Coupon clicks", "count", "behavioral", (5.0, 1.0, 0.5, 0.3, 0.2)),
            Feature("newsletter_signup", "Newsletter signup", "binary", "declared", (0.3, 0.7, 0.1, 0.4, 0.02), 0.2),
            Feature("app_installed", "Has the app installed", "binary", "behavioral", (0.4, 0.75, 0.1, 0.2, 0.02)),
        ),
        breakdown_label="Device",
        breakdown_values=("Mobile", "Desktop", "Tablet"),
        breakdown_by_segment=(
            (0.7, 0.25, 0.05),
            (0.55, 0.35, 0.1),
            (0.75, 0.2, 0.05),
            (0.3, 0.65, 0.05),
            (0.8, 0.15, 0.05),
        ),
        collection_method="tag_or_pixel",
        location="workspace",
        methods=("lookalike", "actalike", "propensity"),
        seed_label="Recent high-value purchasers",
        seed_size=500,
        seed_segment_weights=(0.2, 0.7, 0.02, 0.08, 0.0),
        behavior_label="Shoppers who add to cart and use coupons",
        behavior_features=("cart_adds_28d", "coupon_clicks"),
        behavior_share=0.07,
        outcome=Outcome(
            "purchase",
            "purchase",
            30,
            {"cart_adds_28d": 1.3, "sessions_28d": 0.5, "app_installed": 0.6, "coupon_clicks": 0.3},
            0.05,
        ),
        known_limits=("Cookie churn shortens histories", "Consent coverage varies by market"),
        rng_seed=20261106,
    ),
    DatasetSpec(
        dataset_id="crm",
        title="First-party CRM",
        type_label="First-party CRM",
        summary=(
            "Your customers with tenure, orders, value and email engagement. "
            "Look-alikes, a purchase propensity model, and your own registered model."
        ),
        unit=Unit("person_key", "wb_crm_customer", "customer_id", "cust_", "Customer"),
        n=15000,
        segment_probs=K5,
        segment_labels=("VIP", "Regulars", "Lapsing", "New", "Bargain only"),
        features=(
            Feature("tenure_months", "Tenure (months)", "count", "declared", (48.0, 30.0, 36.0, 3.0, 18.0)),
            Feature("orders_12m", "Orders, 12 months", "count", "behavioral", (14.0, 6.0, 1.5, 1.2, 3.0)),
            Feature("aov_index", "Average order value (index)", "score", "behavioral", (8.0, 5.5, 5.0, 4.5, 2.5)),
            Feature(
                "days_since_order_log", "Days since last order (log)", "score", "behavioral", (2.5, 3.3, 5.3, 2.8, 4.0)
            ),
            Feature("email_open_rate", "Email open rate", "share", "behavioral", (0.55, 0.35, 0.1, 0.45, 0.2), 0.1),
            Feature("loyalty_member", "Loyalty programme member", "binary", "declared", (0.95, 0.6, 0.4, 0.2, 0.3)),
            Feature("returns_rate", "Returns rate", "share", "behavioral", (0.05, 0.08, 0.12, 0.06, 0.2), 0.05),
        ),
        breakdown_label="Customer tier",
        breakdown_values=("Gold", "Silver", "Bronze"),
        breakdown_by_segment=(
            (0.85, 0.15, 0.0),
            (0.25, 0.6, 0.15),
            (0.05, 0.35, 0.6),
            (0.05, 0.25, 0.7),
            (0.0, 0.2, 0.8),
        ),
        collection_method="transaction_record",
        location="workspace",
        methods=("lookalike", "propensity", "byom"),
        seed_label="Top 5% customers by 12-month value",
        seed_size=600,
        seed_segment_weights=(0.85, 0.15, 0.0, 0.0, 0.0),
        outcome=Outcome(
            "purchase",
            "purchase",
            30,
            {"orders_12m": 1.0, "email_open_rate": 0.7, "days_since_order_log": -1.1, "loyalty_member": 0.4},
            0.08,
        ),
        known_limits=("Customers who never bought online are missing", "Email engagement depends on deliverability"),
        rng_seed=20261107,
    ),
    DatasetSpec(
        dataset_id="url_content",
        title="Page content (URL)",
        type_label="Page content (URL)",
        summary=(
            "Pages with topic signals, tone and brand-safety scores. Find "
            "pages that match a content brief, or pages like your best performers."
        ),
        unit=Unit("content_item_key", "wb_publisher_url", "url_id", "url_", "Page"),
        n=6000,
        segment_probs=(0.2, 0.2, 0.2, 0.2, 0.2),
        segment_labels=("Cooking", "Personal finance", "Travel", "Tech reviews", "Local news"),
        features=(
            Feature("topic_food", "Topic signal: food", "score", "contextual", (4.0, 0.2, 1.0, 0.2, 0.8)),
            Feature("topic_money", "Topic signal: money", "score", "contextual", (0.3, 4.0, 0.8, 1.0, 0.8)),
            Feature("topic_travel", "Topic signal: travel", "score", "contextual", (1.0, 0.6, 4.0, 0.4, 0.8)),
            Feature("topic_tech", "Topic signal: technology", "score", "contextual", (0.3, 1.2, 0.5, 4.0, 0.5)),
            Feature("tone_positive", "Positive tone", "share", "contextual", (0.75, 0.5, 0.7, 0.55, 0.35)),
            Feature("brand_safety", "Brand-safety score", "share", "contextual", (0.95, 0.9, 0.92, 0.9, 0.6)),
            Feature("words_log", "Article length (log words)", "score", "contextual", (6.8, 7.2, 7.0, 7.4, 6.2)),
        ),
        breakdown_label="Section",
        breakdown_values=("Lifestyle", "Money", "Travel", "Tech", "News"),
        breakdown_by_segment=(
            (0.85, 0.0, 0.1, 0.0, 0.05),
            (0.05, 0.85, 0.0, 0.05, 0.05),
            (0.1, 0.0, 0.85, 0.0, 0.05),
            (0.0, 0.05, 0.0, 0.9, 0.05),
            (0.05, 0.05, 0.05, 0.05, 0.8),
        ),
        collection_method="crawl_extraction",
        location="workspace",
        methods=("semantic", "lookalike"),
        seed_label="Pages where last campaign performed best",
        seed_size=200,
        seed_segment_weights=(0.75, 0.0, 0.25, 0.0, 0.0),
        brief_label="Weeknight cooking for busy families",
        brief_segment=0,
        known_limits=(
            "Topic signals come from page text, not the audience",
            "Brand-safety scores are provider-assigned",
        ),
        rng_seed=20261108,
    ),
)

BY_ID = {d.dataset_id: d for d in DATASETS}
