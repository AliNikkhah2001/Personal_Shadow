#!/usr/bin/env python3
"""Fetch CC-licensed food images from Wikimedia Commons for calorie vision testing.

Downloads a few representative food images, verifies license is CC0/CC-BY/CC-BY-SA/PD,
and saves them to samples/calorie_vision/input/.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

import requests

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
FILEPATH_URL = "https://commons.wikimedia.org/wiki/Special:FilePath/"

# Search terms for diverse food categories
SEARCH_TERMS = [
    ("rice plate", "rice"),
    ("grilled chicken breast plate", "chicken"),
    ("mixed salad bowl", "salad"),
    ("apple fruit", "fruit"),
    ("spaghetti pasta", "pasta"),
    ("fried egg breakfast", "egg"),
    ("steak plate", "meat"),
    ("yogurt bowl", "yogurt"),
]

LICENSE_WHITELIST = {
    "cc0",
    "cc-by-2.0",
    "cc-by-3.0",
    "cc-by-4.0",
    "cc-by-sa-2.0",
    "cc-by-sa-3.0",
    "cc-by-sa-4.0",
    "public domain",
    "pd-old",
}

HEADERS = {
    "User-Agent": "MindPalaceOS/1.0 (https://github.com/AliNikkhah2001/Personal_Shadow; alinikkhah@example.com) python-requests"
}


def search_commons(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search Wikimedia Commons for images matching query."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": f"{query} filetype:bitmap",
        "srnamespace": 6,  # File namespace
        "srlimit": limit,
        "format": "json",
    }
    r = requests.get(COMMONS_API, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json().get("query", {}).get("search", [])


def get_image_info(filename: str) -> dict[str, Any] | None:
    """Get image metadata including license and direct URL."""
    params = {
        "action": "query",
        "titles": f"File:{filename}",
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|size",
        "iiurlwidth": 1024,
        "format": "json",
    }
    r = requests.get(COMMONS_API, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    for page in pages.values():
        if "imageinfo" in page:
            return page["imageinfo"][0]
    return None


def is_license_ok(info: dict[str, Any]) -> bool:
    """Check if image license is in whitelist."""
    ext = info.get("extmetadata", {})
    license_val = ext.get("License", {}).get("value", "").lower()
    # Also check LicenseShortName
    license_short = ext.get("LicenseShortName", {}).get("value", "").lower()
    return any(lic in license_val for lic in LICENSE_WHITELIST) or any(
        lic in license_short for lic in LICENSE_WHITELIST
    )


def download_image(url: str, dest: Path) -> bool:
    """Download image to destination."""
    try:
        r = requests.get(url, stream=True, headers=HEADERS, timeout=30)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"  Download failed: {e}")
        return False


def sanitize_filename(name: str) -> str:
    """Sanitize for filesystem."""
    return re.sub(r"[^\w\-_.]", "_", name)


def main():
    out_dir = Path("samples/calorie_vision/input")
    out_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    for query, cat in SEARCH_TERMS:
        if downloaded >= 12:
            break
        print(f"\nSearching: {query}")
        try:
            results = search_commons(query, limit=8)
        except Exception as e:
            print(f"  Search failed: {e}")
            continue

        for item in results:
            if downloaded >= 12:
                break
            title = item.get("title", "")
            filename = title.replace("File:", "")
            print(f"  Checking: {filename}")

            try:
                info = get_image_info(filename)
                if not info:
                    continue
                if not is_license_ok(info):
                    license_val = info.get("extmetadata", {}).get("License", {}).get("value", "unknown")
                    print(f"  Skip - license: {license_val}")
                    continue

                url = info.get("thumburl") or info.get("url")
                if not url:
                    continue

                # Download
                safe_name = sanitize_filename(f"{cat}_{filename}")
                dest = out_dir / safe_name
                if dest.exists():
                    print(f"  Already have {dest.name}")
                    downloaded += 1
                    continue

                print(f"  Downloading... ({info.get('width', '?')}x{info.get('height', '?')})")
                if download_image(url, dest):
                    print(f"  Saved: {dest.name}")
                    downloaded += 1
                    time.sleep(0.5)  # be nice to the API
                else:
                    if dest.exists():
                        dest.unlink()
            except Exception as e:
                print(f"  Error: {e}")
                continue

    print(f"\nDone. Downloaded {downloaded} images to {out_dir}")


if __name__ == "__main__":
    main()
