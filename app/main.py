"""Thin CLI entry point — delegates to the orchestrator (Phase 4)."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from app.models import (
    BudgetPreference,
    ErrorResponse,
    NoResultsResponse,
    RecommendationResult,
    UserPreferences,
)
from app.orchestrator import recommend
from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _add_recommend_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--location",
        help="City or area (e.g. Bangalore)",
    )
    parser.add_argument(
        "--budget",
        choices=[b.value for b in BudgetPreference],
        help="Budget tier: low, medium, or high",
    )
    parser.add_argument("--cuisine", help="Cuisine type (comma-separated for OR)")
    parser.add_argument(
        "--min-rating",
        type=float,
        dest="min_rating",
        help="Minimum rating (0–5)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=None,
        help=f"Number of recommendations (default {settings.default_top_n})",
    )
    parser.add_argument(
        "--additional-preferences",
        default=None,
        help="Free-text vibe or extras for the LLM prompt",
    )
    parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="json",
        help="Output format (default json)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Zomato Top 5 — AI restaurant recommendations",
        epilog=(
            "Examples:\n"
            "  python -m app.main --location Bangalore --budget medium "
            "--cuisine Italian --min-rating 4.0\n"
            "  python -m app.main recommend --location Delhi --budget low "
            "--cuisine Indian --min-rating 3.5"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_recommend_arguments(parser)

    subparsers = parser.add_subparsers(dest="command")

    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Load and print sample restaurants from Hugging Face",
    )
    ingest_parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Number of sample restaurants to print",
    )

    filter_parser = subparsers.add_parser(
        "filter",
        help="Filter restaurants by preferences (Phase 2 demo)",
    )
    filter_parser.add_argument("--location", required=True)
    filter_parser.add_argument(
        "--budget",
        required=True,
        choices=[b.value for b in BudgetPreference],
    )
    filter_parser.add_argument("--cuisine", required=True)
    filter_parser.add_argument("--min-rating", type=float, required=True)
    filter_parser.add_argument("--limit", type=int, default=3)

    recommend_parser = subparsers.add_parser(
        "recommend",
        help="Full pipeline: filter + LLM recommendations",
    )
    _add_recommend_arguments(recommend_parser)

    return parser


def _preferences_from_args(args: argparse.Namespace) -> UserPreferences:
    missing = [
        name
        for name, value in (
            ("location", args.location),
            ("budget", args.budget),
            ("cuisine", args.cuisine),
            ("min_rating", args.min_rating),
        )
        if value is None
    ]
    if missing:
        raise SystemExit(
            f"Missing required arguments for recommend: {', '.join(missing)}"
        )

    top_n = args.top_n if args.top_n is not None else settings.default_top_n
    return UserPreferences(
        location=args.location,
        budget=args.budget,
        cuisine=args.cuisine,
        min_rating=args.min_rating,
        additional_preferences=args.additional_preferences,
        top_n=top_n,
    )


def format_table(result: RecommendationResult) -> str:
    lines = ["Recommendations:", ""]
    if result.summary:
        lines.extend([result.summary, ""])
    for item in result.recommendations:
        lines.append(f"#{item.rank} {item.name} ({item.cuisine}) — ★{item.rating}")
        lines.append(f"   Cost: {item.estimated_cost}")
        lines.append(f"   {item.explanation}")
        lines.append("")
    if result.meta.degraded:
        lines.append(
            f"(Degraded mode: {result.meta.degraded_reason or 'fallback'})"
        )
    lines.append(
        f"Considered {result.meta.candidates_considered} candidates, "
        f"showing top {result.meta.top_n}."
    )
    return "\n".join(lines)


def print_response(
    response: RecommendationResult | NoResultsResponse | ErrorResponse,
    *,
    output_format: str = "json",
) -> None:
    if output_format == "table" and isinstance(response, RecommendationResult):
        print(format_table(response))
        return
    print(response.model_dump_json(indent=2))


def run_recommend(args: argparse.Namespace) -> int:
    prefs = _preferences_from_args(args)
    response = recommend(prefs)
    print_response(response, output_format=args.format)

    if isinstance(response, ErrorResponse):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "ingest":
        from app.ingestion.loader import load_restaurants

        restaurants = load_restaurants()
        limit = min(args.limit, len(restaurants))
        for restaurant in restaurants[:limit]:
            print(restaurant.model_dump_json(indent=2))
        return 0

    if args.command == "filter":
        from app.filtering.filter_service import filter_candidates
        from app.ingestion.loader import load_restaurants

        load_restaurants()
        preferences = UserPreferences(
            location=args.location,
            budget=args.budget,
            cuisine=args.cuisine,
            min_rating=args.min_rating,
        )
        batch = filter_candidates(preferences)
        print(
            json.dumps(
                {
                    "candidates_found": len(batch.candidates),
                    "filter_stats": batch.filter_stats.model_dump(),
                    "top": [
                        {
                            "name": r.name,
                            "rating": r.rating,
                            "cuisines": r.cuisines,
                        }
                        for r in batch.candidates[: args.limit]
                    ],
                },
                indent=2,
            )
        )
        return 0

    if args.command == "recommend" or (
        args.command is None and args.location is not None
    ):
        return run_recommend(args)

    if args.command is None:
        parser.print_help()
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
