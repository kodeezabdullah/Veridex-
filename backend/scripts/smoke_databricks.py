"""Smoke-test both real facility endpoints after backend/.env is configured."""

from __future__ import annotations

import argparse
import json

from fastapi.testclient import TestClient

from backend.main import app


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capability", default="ICU")
    parser.add_argument("--state")
    parser.add_argument("--district")
    parser.add_argument("--unique-id", help="Optional known ID; otherwise the first list result is used.")
    args = parser.parse_args()

    filters = {key: value for key, value in {
        "capability": args.capability,
        "state": args.state,
        "district": args.district,
    }.items() if value}

    with TestClient(app) as client:
        list_response = client.get("/api/facilities", params=filters)
        print(f"GET /api/facilities -> {list_response.status_code}")
        if list_response.status_code != 200:
            print(list_response.text)
            return 1

        facilities = list_response.json()
        print(f"facilities returned: {len(facilities)}")
        if facilities:
            print(json.dumps(facilities[:3], indent=2))

        unique_id = args.unique_id or (facilities[0]["unique_id"] if facilities else None)
        if unique_id is None:
            print("No facility ID is available for the detail smoke test.")
            return 0

        detail_response = client.get(f"/api/facility/{unique_id}")
        print(f"GET /api/facility/{unique_id} -> {detail_response.status_code}")
        print(json.dumps(detail_response.json(), indent=2))
        return 0 if detail_response.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
