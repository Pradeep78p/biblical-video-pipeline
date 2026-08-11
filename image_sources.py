"""
Wrappers around LICENSED image source APIs only — Wikimedia Commons, Met
Museum, Smithsonian Open Access, Unsplash. Deliberately does NOT include
generic web/Google Image search, which returns copyrighted images with no
clear usage rights — not safe to embed in 1200 published teaching videos.

Each search_* function returns a list of candidate dicts:
    {"source", "title", "image_url", "source_page_url", "license"}
Caller (fetch_images script) picks the first usable candidate and downloads it.
"""
import requests

import config


def search_wikimedia(query: str, max_results: int = None) -> list:
    """Wikimedia Commons — no API key required."""
    max_results = max_results or config.MAX_CANDIDATES_PER_SOURCE
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap",
        "gsrnamespace": 6,  # File namespace
        "gsrlimit": max_results,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 1024,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})
    except Exception:
        return []

    results = []
    for page in pages.values():
        infos = page.get("imageinfo", [])
        if not infos:
            continue
        info = infos[0]
        meta = info.get("extmetadata", {})
        license_short = meta.get("LicenseShortName", {}).get("value", "unknown")
        results.append({
            "source": "wikimedia",
            "title": page.get("title", "").replace("File:", ""),
            "image_url": info.get("thumburl") or info.get("url"),
            "source_page_url": info.get("descriptionurl"),
            "license": license_short,
        })
    return results


def search_met_museum(query: str, max_results: int = None) -> list:
    """Met Museum Open Access — no API key required. All results are CC0."""
    max_results = max_results or config.MAX_CANDIDATES_PER_SOURCE
    search_url = "https://collectionapi.metmuseum.org/public/collection/v1/search"
    try:
        resp = requests.get(
            search_url,
            params={"q": query, "hasImages": "true"},
            timeout=15,
        )
        resp.raise_for_status()
        object_ids = (resp.json().get("objectIDs") or [])[:max_results]
    except Exception:
        return []

    results = []
    for obj_id in object_ids:
        try:
            obj_resp = requests.get(
                f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{obj_id}",
                timeout=15,
            )
            obj_resp.raise_for_status()
            obj = obj_resp.json()
        except Exception:
            continue
        image_url = obj.get("primaryImage")
        if not image_url:
            continue
        results.append({
            "source": "met_museum",
            "title": obj.get("title", ""),
            "image_url": image_url,
            "source_page_url": obj.get("objectURL"),
            "license": "CC0",
        })
    return results


def search_smithsonian(query: str, max_results: int = None) -> list:
    """Smithsonian Open Access — requires a free api.data.gov key. All CC0."""
    if not config.SMITHSONIAN_API_KEY:
        return []
    max_results = max_results or config.MAX_CANDIDATES_PER_SOURCE
    url = "https://api.si.edu/openaccess/api/v1.0/search"
    params = {
        "q": query,
        "api_key": config.SMITHSONIAN_API_KEY,
        "rows": max_results,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        rows = resp.json().get("response", {}).get("rows", [])
    except Exception:
        return []

    results = []
    for row in rows:
        media = (
            row.get("content", {})
            .get("descriptiveNonRepeating", {})
            .get("online_media", {})
            .get("media", [])
        )
        if not media:
            continue
        image_url = media[0].get("content")
        if not image_url:
            continue
        results.append({
            "source": "smithsonian",
            "title": row.get("title", ""),
            "image_url": image_url,
            "source_page_url": row.get("content", {}).get("descriptiveNonRepeating", {}).get("guid"),
            "license": "CC0",
        })
    return results


def search_unsplash(query: str, max_results: int = None) -> list:
    """Unsplash — for landscape/geographic backdrop photos. Requires free API key."""
    if not config.UNSPLASH_ACCESS_KEY:
        return []
    max_results = max_results or config.MAX_CANDIDATES_PER_SOURCE
    url = "https://api.unsplash.com/search/photos"
    headers = {"Authorization": f"Client-ID {config.UNSPLASH_ACCESS_KEY}"}
    params = {"query": query, "per_page": max_results}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        items = resp.json().get("results", [])
    except Exception:
        return []

    results = []
    for item in items:
        results.append({
            "source": "unsplash",
            "title": item.get("description") or item.get("alt_description") or "",
            "image_url": item.get("urls", {}).get("regular"),
            "source_page_url": item.get("links", {}).get("html"),
            "license": "Unsplash License (free to use)",
        })
    return results


SOURCE_FUNCTIONS = {
    "wikimedia": search_wikimedia,
    "met_museum": search_met_museum,
    "smithsonian": search_smithsonian,
    "unsplash": search_unsplash,
}


def search_all_sources_in_priority(query: str) -> list:
    """
    Try each source in config.IMAGE_SOURCE_PRIORITY order, return candidates
    from the FIRST source that returns any results. Caller can still choose
    among the returned candidates.
    """
    for source_name in config.IMAGE_SOURCE_PRIORITY:
        fn = SOURCE_FUNCTIONS.get(source_name)
        if not fn:
            continue
        results = fn(query)
        if results:
            return results
    return []
