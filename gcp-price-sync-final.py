#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import json
import os
import re
import sys
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None  # Fallback if requests isn't installed; URL fetching will error with guidance


# -----------------------------
# Data models
# -----------------------------

@dataclasses.dataclass
class SKURecord:
    service_name: str
    sku_name: str
    sku_id: str
    description: str
    category_resource_family: Optional[str]
    category_usage_type: Optional[str]
    region: Optional[str]
    currency: str
    unit_price: Optional[float]
    machine_family: Optional[str]
    machine_type: Optional[str]
    billing_unit: Optional[str]
    effective_time: Optional[str]


# -----------------------------
# Utilities
# -----------------------------

def parse_money(money_obj: Dict[str, Any]) -> float:
    if not isinstance(money_obj, dict):
        return 0.0
    units = int(money_obj.get("units", 0) or 0)
    nanos = int(money_obj.get("nanos", 0) or 0)
    return float(units) + float(nanos) / 1_000_000_000.0


def parse_effective_time(s: Optional[str]) -> Optional[dt.datetime]:
    if not s:
        return None
    try:
        # Example: "2024-07-01T00:00:00Z"
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return dt.datetime.fromisoformat(s)
    except Exception:
        return None


# -----------------------------
# Processor
# -----------------------------

class SKUCatalogProcessor:
    MACH_FAMILY_PATTERN = re.compile(
        r"\b(?:(E2|N1|N2|N2D|T2A|T2D|C2|C2D|A2|G2|M1|M2|M3|H3|Z3))\b",
        flags=re.IGNORECASE,
    )

    MACHINE_TYPE_PATTERN = re.compile(
        r"\b([a-z]\d?(?:[a-z]\d?)?-?\w*?-(?:micro|small|medium|large|x?\d+|standard-\d+|highmem-\d+|highcpu-\d+|megamen-\d+|ultramem-\d+))\b",
        flags=re.IGNORECASE,
    )

    def __init__(self, currency: str = "USD") -> None:
        self.currency = currency

    def extract_machine_family(self, text: str) -> Optional[str]:
        if not text:
            return None
        match = self.MACH_FAMILY_PATTERN.search(text)
        if not match:
            return None
        return match.group(1).upper()

    def extract_machine_type(self, text: str) -> Optional[str]:
        if not text:
            return None
        # Look for patterns like n2-standard-4, e2-micro, c2d-highcpu-16, etc.
        match = self.MACHINE_TYPE_PATTERN.search(text)
        if match:
            return match.group(1).lower()
        # Fallback: explicit common types
        fallback_match = re.search(r"\b([enctagmhz]\d[a-z]?-[a-z]+-\d+)\b", text, re.IGNORECASE)
        return fallback_match.group(1).lower() if fallback_match else None

    def choose_latest_pricing(self, pricing_info_list: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not pricing_info_list:
            return None
        # Sort by effectiveTime (desc); if absent, treat as oldest
        def key_fn(pi: Dict[str, Any]) -> Tuple[int, float]:
            ts = parse_effective_time(pi.get("effectiveTime"))
            return (1 if ts else 0, ts.timestamp() if ts else 0.0)

        return sorted(pricing_info_list, key=key_fn, reverse=True)[0]

    def compute_unit_price_and_unit(self, pricing_expr: Dict[str, Any]) -> Tuple[Optional[float], Optional[str]]:
        if not pricing_expr:
            return (None, None)
        # tieredRates may exist; take the first tier as representative unit price
        tiered_rates = pricing_expr.get("tieredRates") or []
        if tiered_rates:
            price = parse_money(tiered_rates[0].get("unitPrice") or {})
        else:
            price = parse_money(pricing_expr.get("unitPrice") or {})
        unit = pricing_expr.get("usageUnitDescription") or pricing_expr.get("usageUnit")
        if isinstance(unit, str):
            unit = unit.strip()
        return (price if price > 0 else None, unit)

    def normalize_region(self, sku: Dict[str, Any]) -> Optional[str]:
        # regions listed under serviceRegions for the SKU; sometimes ["global"]
        regions: List[str] = sku.get("serviceRegions") or []
        if not regions:
            return None
        # Some SKUs apply to multiple regions; keep 'global' or the first region
        if "global" in regions:
            return "global"
        return regions[0]

    def to_records(self, service_name: str, sku_items: Iterable[Dict[str, Any]]) -> List[SKURecord]:
        records: List[SKURecord] = []
        for sku in sku_items:
            category = sku.get("category") or {}
            pricing_info = sku.get("pricingInfo") or []
            latest = self.choose_latest_pricing(pricing_info)
            pricing_expr = (latest or {}).get("pricingExpression") or {}
            unit_price, unit = self.compute_unit_price_and_unit(pricing_expr)
            desc = sku.get("description") or sku.get("displayName") or ""
            record = SKURecord(
                service_name=service_name,
                sku_name=sku.get("name", ""),
                sku_id=sku.get("skuId", ""),
                description=desc,
                category_resource_family=category.get("resourceFamily"),
                category_usage_type=category.get("usageType"),
                region=self.normalize_region(sku),
                currency=pricing_expr.get("baseUnit") or (latest or {}).get("currency", "USD"),
                unit_price=unit_price,
                machine_family=self.extract_machine_family(desc),
                machine_type=self.extract_machine_type(desc),
                billing_unit=unit,
                effective_time=(latest or {}).get("effectiveTime"),
            )
            records.append(record)
        return records


# -----------------------------
# Fetcher (Cloud Billing Catalog API)
# -----------------------------

class BillingCatalogClient:
    BASE_URL = "https://cloudbilling.googleapis.com/v1"

    def __init__(self, api_key: Optional[str]) -> None:
        self.api_key = api_key
        if requests is None:
            raise RuntimeError(
                "The 'requests' package is required to fetch from the Cloud Billing API. Install with: pip install requests"
            )
        if not api_key:
            raise RuntimeError(
                "Missing API key. Set GCP_API_KEY env var or pass --api-key to use the Cloud Billing Catalog API."
            )

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        params = {**params, "key": self.api_key}
        url = f"{self.BASE_URL}{path}"
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def list_services(self) -> List[Dict[str, Any]]:
        resp = self._get("/services", params={})
        return resp.get("services", [])

    def find_service_by_display_name(self, display_name: str) -> Optional[Dict[str, Any]]:
        display_name_l = display_name.strip().lower()
        for svc in self.list_services():
            if str(svc.get("displayName", "")).strip().lower() == display_name_l:
                return svc
        return None

    def list_skus(
        self,
        service_name: str,
        currency: str = "USD",
        page_size: int = 1000,
        max_pages: int = 100,
        sleep_between_pages_sec: float = 0.2,
    ) -> Iterable[Dict[str, Any]]:
        # service_name must be like "services/6F81-5844-456A"
        next_token: Optional[str] = None
        pages = 0
        while True:
            params = {"currencyCode": currency, "pageSize": page_size}
            if next_token:
                params["pageToken"] = next_token
            obj = self._get(f"/{service_name}/skus", params=params)
            for sku in obj.get("skus", []):
                yield sku
            next_token = obj.get("nextPageToken")
            pages += 1
            if not next_token or pages >= max_pages:
                break
            time.sleep(sleep_between_pages_sec)


# -----------------------------
# CSV export
# -----------------------------

def write_records_to_csv(records: Iterable[SKURecord], out_path: str) -> None:
    fieldnames = [
        "service_name",
        "sku_name",
        "sku_id",
        "description",
        "category_resource_family",
        "category_usage_type",
        "region",
        "currency",
        "unit_price",
        "machine_family",
        "machine_type",
        "billing_unit",
        "effective_time",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(dataclasses.asdict(r))


# -----------------------------
# CLI
# -----------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Fetch and process GCP Cloud Billing Catalog SKUs into a CSV summary (Python 3.9+).",
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--fetch",
        action="store_true",
        help="Fetch from Cloud Billing Catalog API (requires API key)",
    )
    src.add_argument(
        "--input-json",
        help="Path to a local JSON file containing SKUs (full services.skus.list response or array)",
    )

    p.add_argument(
        "--service-name",
        default="Compute Engine",
        help="Display name of the service to fetch (default: Compute Engine)",
    )
    p.add_argument(
        "--service-id",
        help="If known, the service resource name (e.g., services/6F81-5844-456A). Overrides --service-name.",
    )
    p.add_argument(
        "--currency",
        default="USD",
        help="Currency code for pricing (default: USD)",
    )
    p.add_argument(
        "--api-key",
        default=os.environ.get("GCP_API_KEY"),
        help="API key for the Cloud Billing Catalog API. Defaults to $GCP_API_KEY.",
    )
    p.add_argument(
        "--out",
        required=True,
        help="Output CSV path",
    )
    p.add_argument(
        "--filter-region",
        help="Optional region filter (e.g., us-central1). If set, only matching records are included.",
    )
    p.add_argument(
        "--only-compute",
        action="store_true",
        help="When reading --input-json, only include SKUs for Compute Engine-like descriptions",
    )
    return p


def load_local_skus(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Accept either a dict with key "skus" or a list
    if isinstance(data, dict) and "skus" in data:
        return list(data["skus"])  # type: ignore[return-value]
    if isinstance(data, list):
        return data  # type: ignore[return-value]
    raise ValueError("Unsupported JSON structure. Provide either an array of SKUs or an object with a 'skus' array.")


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    processor = SKUCatalogProcessor(currency=args.currency)

    records: List[SKURecord] = []
    service_label = args.service_name

    if args.fetch:
        client = BillingCatalogClient(api_key=args.api_key)
        service_name = args.service_id
        if not service_name:
            svc = client.find_service_by_display_name(args.service_name)
            if not svc:
                raise SystemExit(f"Service '{args.service_name}' not found. Use --service-id to set it explicitly.")
            service_name = svc.get("name")
            service_label = svc.get("displayName", args.service_name)
        sku_iter = client.list_skus(service_name=service_name, currency=args.currency)
        records = processor.to_records(service_label, sku_iter)

    else:
        skus = load_local_skus(args.input_json)
        if args.only_compute:
            # Simple heuristic filter for Compute Engine-related SKUs
            keywords = [
                "Compute Engine",
                "N1 ", "N2 ", "E2 ", "C2 ", "C2D ", "T2A ", "T2D ", "A2 ", "G2 ", "M2 ",
                "vCPU", "RAM", "Core", "vCPU hour",
            ]
            
            def looks_like_compute(sku: Dict[str, Any]) -> bool:
                desc = str(sku.get("description") or sku.get("displayName") or "")
                return any(k.lower() in desc.lower() for k in keywords)

            skus = [s for s in skus if looks_like_compute(s)]
        records = processor.to_records(service_label, skus)

    # Apply region filter if requested
    if args.filter_region:
        region_norm = args.filter_region.strip().lower()
        records = [r for r in records if (r.region or "").lower() == region_norm]

    # Normalize currency output to the requested currency label
    for r in records:
        r.currency = args.currency

    # Write CSV
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    write_records_to_csv(records, args.out)

    print(f"Wrote {len(records)} records to {args.out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        raise SystemExit(130)