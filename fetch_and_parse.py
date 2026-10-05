"""
fetch_and_parse.py
==================
Fetches all videos from the Big Piano Small Piano YouTube channel,
parses descriptions for piano score links and credits, and writes
the results to src/data/videos.json and src/data/scores.json.

Usage:
    export YT_API_KEY="your_key_here"
    python fetch_and_parse.py

GitHub Actions will set YT_API_KEY via repository secrets.
"""

import os
import json
import re
import sys
import time
import requests
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
API_KEY     = os.environ.get("YT_API_KEY")
CHANNEL_ID  = "UCsKtOGplqKz3uGt9XD8VexQ"
PLAYLIST_ID = "UUsKtOGplqKz3uGt9XD8VexQ"   # UC → UU shortcut
BASE_URL    = "https://www.googleapis.com/youtube/v3"
OUTPUT_DIR  = os.path.join("src", "data")

# ── Regex patterns ─────────────────────────────────────────────────────────────

# Score / sheet music download links
SCORE_LINK_PATTERNS = [
    r"https?://(?:drive|docs)\.google\.com/\S+",
    r"https?://(?:www\.)?musescore\.com/\S+",
    r"https?://(?:www\.)?dropbox\.com/\S+",
    r"https?://(?:www\.)?imslp\.org/\S+",
    r"https?://(?:www\.)?mediafire\.com/\S+",
    r"https?://\S+\.pdf(?:\?\S*)?",
    r"https?://(?:www\.)?scribd\.com/\S+",
    r"https?://1drv\.ms/\S+",
    r"https?://\S+\.gumroad\.com/\S+",       # ← your own scores
    r"https?://gumroad\.com/\S+",
    r"https?://(?:www\.)?patreon\.com/\S+",  # ← ChewieMelodies
    r"https?://(?:www\.)?chaconnescott\.(?:gumroad\.com|com)/\S+",
]

# Credit attribution lines
#
# Each pattern's first capture group is a *candidate* credit string. It is then
# run through clean_credit_candidate() which trims connective words / trailing
# prose, so the free-text "by" patterns below can stay fairly loose.
CREDIT_PATTERNS = [
    # "Piano Sheet @AnimuzAnimePiano" or "Piano Sheets @name1 @name2 @name3"
    r"piano\s+sheets?\s+((?:@[\w-]+\s*&?\s*)+)",
    # "Piano Sheet from @AnimuzAnimePiano"
    r"piano\s+sheets?\s+from\s+@?([\w-]+)",
    # "By @ChaconneScott" at the start of a line
    r"(?:^|\n)\s*by\s+@([\w-]+)",
    # "(Credits to @StarryCosmoss-Piano)" / "(Credits: Animuz)" / "(Credits to Samuel Henry)"
    r"\(\s*credits?\s*(?:to|:)?\s*@?([\w][\w .'-]+?)\s*(?:\s+for\b[^)]*)?\)",
    # "based on ChaconneScott's arrangement"
    r"based\s+on\s+@?([\w-]+)'s\s+arrangement",
    # "credits to ChaconneScott for sharing" (not always parenthesised)
    r"credits?\s+to\s+@?([\w-]+)\s+for\s+sharing",
    # "obtained via @ChewieMelodies" — require an @handle so the English word
    # "via" in prose does not match.
    r"(?:obtained\s+)?via\s+@([\w-]+)",
    # "Arranged by: NAME", "arr. NAME", "Score by: NAME", "Transcribed by NAME"
    r"(?:arranged|arr\.)\s+by[:\-\s]+([^\n\r]{2,60})",
    r"(?:score|sheet\s*music)\s+by[:\-\s]+([^\n\r]{2,60})",
    r"transcri(?:bed|ption)\s+(?:by\s+)?([^\n\r]{2,60})",
]

# Connective / filler words that are never a credit on their own. Used to trim
# free-text captures and to drop stray tokens.
CREDIT_STOPWORDS = {
    "a", "an", "and", "the", "to", "of", "in", "on", "for", "with", "by",
    "from", "its", "it", "this", "that", "those", "these", "is", "was", "are",
    "be", "as", "at", "or", "but", "not", "no", "my", "me", "i", "you", "your",
    "his", "her", "their", "our", "credit", "credits", "sharing", "share",
    "do", "check", "out", "please", "thanks", "thank", "here", "above", "below",
    "some", "parts", "part", "cover", "sheet", "sheets", "arrangement",
    "arranged", "based", "referenced", "reference", "original", "improvisation",
    "improvisations", "transposed", "key", "focus", "more", "throughout",
    "piece", "image", "swimming", "peacefully", "frogs", "hope", "enjoy",
    "owners", "owner", "respective", "who", "created", "them", "channel",
    "free", "everyone", "hey",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def check_api_key():
    if not API_KEY:
        print("ERROR: YT_API_KEY environment variable is not set.", file=sys.stderr)
        print("Set it with:  export YT_API_KEY='your_key_here'", file=sys.stderr)
        sys.exit(1)


def slugify(text: str) -> str:
    """Convert a video title to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text[:80].strip("-")


def yt_get(endpoint: str, params: dict) -> dict:
    """Make a YouTube Data API v3 GET request with retry on 429."""
    params["key"] = API_KEY
    url = f"{BASE_URL}/{endpoint}"
    for attempt in range(3):
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code == 429:
            wait = 2 ** attempt * 5
            print(f"  Rate limited — waiting {wait}s …")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()


# ── Fetching ───────────────────────────────────────────────────────────────────

def fetch_all_video_ids() -> list[str]:
    """Page through the uploads playlist and collect every video ID."""
    video_ids = []
    page_token = None
    print("Fetching video IDs from uploads playlist …")

    while True:
        params = {
            "part":       "contentDetails",
            "playlistId": PLAYLIST_ID,
            "maxResults": 50,
        }
        if page_token:
            params["pageToken"] = page_token

        data       = yt_get("playlistItems", params)
        items      = data.get("items", [])
        page_ids   = [i["contentDetails"]["videoId"] for i in items]
        video_ids += page_ids
        print(f"  … {len(video_ids)} IDs collected")

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return video_ids


def fetch_video_details(video_ids: list[str]) -> list[dict]:
    """Batch-fetch snippet + statistics for up to 50 IDs per request."""
    all_videos = []
    print(f"Fetching details for {len(video_ids)} videos …")

    # Split into chunks of 50 (API maximum)
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        params = {
            "part": "snippet,statistics,contentDetails",
            "id":   ",".join(chunk),
        }
        data = yt_get("videos", params)
        for item in data.get("items", []):
            s   = item["snippet"]
            st  = item.get("statistics", {})
            cd  = item.get("contentDetails", {})

            # Best available thumbnail
            thumbs = s.get("thumbnails", {})
            thumb  = (
                thumbs.get("maxres") or
                thumbs.get("standard") or
                thumbs.get("high") or
                thumbs.get("medium") or
                {}
            ).get("url", "")

            all_videos.append({
                "videoId":      item["id"],
                "title":        s.get("title", ""),
                "description":  s.get("description", ""),
                "publishedAt":  s.get("publishedAt", ""),
                "thumbnail":    thumb,
                "viewCount":    int(st.get("viewCount", 0)),
                "likeCount":    int(st.get("likeCount", 0)),
                "commentCount": int(st.get("commentCount", 0)),
                "duration":     cd.get("duration", ""),  # ISO 8601 e.g. PT4M33S
                "slug":         slugify(s.get("title", item["id"])),
                "channelTitle": s.get("channelTitle", "Big Piano Small Piano"),
            })

        print(f"  … details fetched for {min(i + 50, len(video_ids))}/{len(video_ids)}")

    # Sort newest first
    all_videos.sort(key=lambda v: v["publishedAt"], reverse=True)
    return all_videos


# ── Parsing ────────────────────────────────────────────────────────────────────

def extract_score_links(description: str) -> list[str]:
    """Return deduplicated list of score download URLs found in a description."""
    found = []
    for pattern in SCORE_LINK_PATTERNS:
        matches = re.findall(pattern, description, re.IGNORECASE)
        found.extend(matches)

    # Clean trailing punctuation that often gets caught in grabs
    cleaned = []
    for url in found:
        url = re.sub(r"[,;)\]\"'>]+$", "", url)
        cleaned.append(url)

    return list(dict.fromkeys(cleaned))   # deduplicate, preserve order


# Map shorthand names to full correct credits
# Your own channel names — never show these as credits
SELF_NAMES = {
    "bigpianosmallpiano", "big piano small piano", "bigpiano",
    "bigpianosmallpiano", "piano small piano", "small piano",
}

# Your own video that you arranged yourself
SELF_ARRANGED_SLUGS = {
    "genshin-ost-pensees-tranquilles-secret-summer-paradise-soothing-bgm-piano-cover",
    "genshin-ost-pensees-tranquilles-secret-summer-paradise-soothing-bgm-piano-cover-piano-sheet",
}

# Map shorthand / variant names (lower-cased) to the canonical credit string.
NAME_CORRECTIONS = {
    "animuz":               "AnimuzAnimePiano",
    "animuzanimepiano":     "AnimuzAnimePiano",
    "chaconne":             "ChaconneScott",
    "chacon":               "ChaconneScott",
    "chaconnescott":        "ChaconneScott",
    "chewie":               "ChewieMelodies",
    "chewiemelodies":       "ChewieMelodies",
    "waragon":              "WaragonSom",
    "waragonsom":           "WaragonSom",
    "starrycosmos":         "StarryCosmoss-Piano",
    "starrycosmos-piano":   "StarryCosmoss-Piano",
    "starrycosmoss-piano":  "StarryCosmoss-Piano",
    "wangzichen962":        "wangzichen962",
    "haoyiwang":            "Haoyi Wang",
    "marupiano":            "MaruPiano",
    "marupiano999":         "MaruPiano",
    "animenz":              "Animenz",
    "animenzzz":            "Animenz",
}


def clean_credit_candidate(raw: str) -> str:
    """Trim a raw regex capture down to a plausible credit name.

    - keeps an @handle verbatim (minus the @)
    - otherwise keeps the leading run of Capitalised words (a person / channel
      name like "Samuel Henry"), stopping at the first lower-case filler word,
      punctuation, or the 3rd word
    Returns "" when nothing name-like remains.
    """
    raw = raw.strip().strip("([{}])").strip()
    if not raw:
        return ""

    # Split off anything after a comma / paren / colon — that's prose, not a name
    raw = re.split(r"[,:()\[\]\n\r]", raw, 1)[0].strip()

    m = re.match(r"@([\w-]+)", raw)
    if m:
        return m.group(1)

    words = raw.split()
    name_words: list[str] = []
    for w in words[:4]:
        stripped = w.strip(".,;&")
        if not stripped:
            break
        if stripped.lower() in CREDIT_STOPWORDS:
            break
        # A name token starts with a letter/digit; stop at all-lower-case prose
        # once we already have at least one name word.
        if name_words and stripped[:1].islower():
            break
        name_words.append(stripped)
        if len(name_words) == 3:
            break

    return " ".join(name_words)

def get_credit_fallback(links: list[str]) -> str:
    """If no valid credit found, infer source from the download link."""
    for link in links:
        if "bigpianosmallpiano.gumroad.com" in link: return "Big Piano Small Piano"
        if "musescore.com"    in link: return "MuseScore"
        if "drive.google.com" in link: return "Google Drive"
        if "gumroad.com"      in link: return "Gumroad"
        if "dropbox.com"      in link: return "Dropbox"
        if "patreon.com"      in link: return "Patreon"
        if "mediafire.com"    in link: return "MediaFire"
        if ".pdf"             in link: return "PDF Download"
    return ""

def extract_credits(description: str, slug: str = "", links: list = []) -> list[str]:
    """Return list of attribution strings found in a description."""
    # Your own self-arranged piece — credit yourself
    if slug in SELF_ARRANGED_SLUGS:
        return ["Big Piano Small Piano"]

    found = []
    for pattern in CREDIT_PATTERNS:
        matches = re.findall(pattern, description, re.IGNORECASE | re.MULTILINE)
        for m in matches:
            # A group like "@name1 @name2 & @name3" → each handle separately;
            # anything else is a single free-text candidate.
            if m.count("@") > 1:
                candidates = [f"@{h}" for h in re.findall(r"@([\w-]+)", m)]
            else:
                candidates = [m]

            for cand in candidates:
                credit = clean_credit_candidate(cand)
                if len(credit) < 2 or len(credit) > 60:
                    continue
                if credit.lower() in CREDIT_STOPWORDS:
                    continue
                if credit.lower() in SELF_NAMES:
                    continue
                # Apply name corrections (whole string, then bare token)
                corrected = NAME_CORRECTIONS.get(
                    credit.lower(),
                    NAME_CORRECTIONS.get(credit, credit)
                )
                if corrected.lower() in SELF_NAMES:
                    continue
                found.append(corrected)

    # Case-insensitive dedupe, keep first-seen casing
    result = []
    seen = set()
    for c in found:
        if c.lower() not in seen:
            seen.add(c.lower())
            result.append(c)

    # If nothing found, fall back to link source label
    if not result and links:
        fallback = get_credit_fallback(links)
        if fallback:
            result = [fallback]

    return result

def parse_scores(videos: list[dict]) -> list[dict]:
    """Build the scores list from all video descriptions."""
    scores = []
    for v in videos:
        links   = extract_score_links(v["description"])
        credits = extract_credits(v["description"], v["slug"], links)
        if links:
            scores.append({
                "videoId":    v["videoId"],
                "title":      v["title"],
                "slug":       v["slug"],
                "thumbnail":  v["thumbnail"],
                "publishedAt": v["publishedAt"],
                "scoreLinks": links,
                "credits":    credits if credits else ["Big Piano Small Piano"],
            })
    return scores


# ── Output ─────────────────────────────────────────────────────────────────────

def write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Written → {path}  ({len(data)} records)")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    check_api_key()

    print("=" * 55)
    print("  Big Piano Small Piano — YouTube Data Sync")
    print(f"  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 55)

    video_ids = fetch_all_video_ids()
    videos    = fetch_video_details(video_ids)
    scores    = parse_scores(videos)

    print("\nSaving data files …")
    write_json(os.path.join(OUTPUT_DIR, "videos.json"), videos)
    write_json(os.path.join(OUTPUT_DIR, "scores.json"), scores)

    print(f"\n✓ Done. {len(videos)} videos, {len(scores)} score entries.")


if __name__ == "__main__":
    main()
