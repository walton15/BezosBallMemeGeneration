"""Download the rendered PDF preview of a PostGrid postcard.

Useful for checking how a card actually prints - whether the front survives
the bleed trim, and whether the back art clears the address block - without
mailing anything.

The preview is NOT fetched in CI on purpose: the rendered back shows the
recipient's address, and this repo's Actions logs are public. Run it locally.

    export POSTGRID_API_KEY=test_sk_...
    python fetch_postcard_preview.py postcard_jbqUucz8LYCWgfzChvoViQ

Writes previews/<id>.pdf, which is gitignored. Treat the signed URL it prints
as sensitive: anyone with it can see the addressed card.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from send_weekly_postcard import API_URL, USER_AGENT

OUT_DIR = "previews"


def api_get(path, api_key):
    request = urllib.request.Request(
        path,
        headers={"x-api-key": api_key, "User-Agent": USER_AGENT},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        sys.exit("ERROR: PostGrid returned HTTP {}\n{}".format(e.code, body))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("postcard_id", nargs="?",
                        help="postcard_... id; omit to list recent postcards")
    parser.add_argument("--limit", type=int, default=10,
                        help="how many to list when no id is given")
    args = parser.parse_args()

    api_key = os.environ.get("POSTGRID_API_KEY")
    if not api_key:
        sys.exit("ERROR: POSTGRID_API_KEY is not set")

    if not args.postcard_id:
        listing = api_get(
            "{}?limit={}".format(API_URL, args.limit), api_key)
        for item in listing.get("data", []):
            print("{}  {:<10} {:<6} {}".format(
                item.get("id"), item.get("status"), item.get("size"),
                item.get("description", "")))
        return 0

    card = api_get("{}/{}".format(API_URL, args.postcard_id), api_key)
    print("id:          {}".format(card.get("id")))
    print("status:      {}".format(card.get("status")))
    print("size:        {}".format(card.get("size")))
    print("live:        {}".format(card.get("live")))
    print("description: {}".format(card.get("description", "")))

    url = card.get("url")
    if not url:
        print("\nNo preview URL yet - PostGrid is still rendering. "
              "Re-run in a few seconds.")
        return 1

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, "{}.pdf".format(card.get("id")))
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    with open(out, "wb") as f:
        f.write(data)

    print("\nSaved {} ({:.0f} KB)".format(out, len(data) / 1024))
    print("This PDF shows the addressed card - do not share it publicly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
