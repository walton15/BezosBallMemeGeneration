"""Mail one meme from weekly_mail_meme/ as a PostGrid postcard.

Run weekly by .github/workflows/weekly_postcard.yml. Each run picks the *next*
image in ascending filename order (tracked in weekly_postcard_state.json), so
every week gets a new one and nothing repeats.

The image is not uploaded to PostGrid directly. PostGrid renders an HTML string
for each side, so the JPG is referenced by a public raw.githubusercontent.com
URL pinned to the current commit SHA (image_source "url"), or inlined as a
base64 data URI if the repo is private (image_source "base64").

Addresses are read from env, not from the committed config: this repo is
public, so a real street address must never be committed to it. The config
file keeps placeholders only, which is what dry runs fall back to.

Env:
  POSTGRID_API_KEY  required unless --dry-run (test_sk_... or live_sk_...)
  POSTCARD_TO       JSON object: the recipient address
  POSTCARD_FROM     JSON object: the return address
  IMAGE_BASE_URL    optional; overrides the derived raw.githubusercontent URL
  GITHUB_REPOSITORY / GITHUB_SHA  used to derive that URL in Actions

Exit codes: 0 sent (or skipped/dry-run), 1 error, 2 no images left to send.
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

API_URL = "https://api.postgrid.com/print-mail/v1/postcards"
USER_AGENT = ("BezosBallMemeGeneration/1.0 "
              "(+https://github.com/walton15/BezosBallMemeGeneration)")
CONFIG_PATH = "postcard_config.json"
STATE_PATH = "weekly_postcard_state.json"
IMAGE_EXTS = (".jpg", ".jpeg", ".png")

# Postcard trim sizes PostGrid accepts, in inches (width, height).
SIZES = {"6x4": (6.0, 4.0), "9x6": (9.0, 6.0), "11x6": (11.0, 6.0)}

# Back-of-card layout. The right side and the bottom strip must stay clear for
# the address block and the USPS barcode, so art is confined to the left.
MARGIN_IN = 0.25
BOTTOM_CLEAR_IN = 0.95
ART_WIDTH_FRAC = 0.45

# PostGrid composites the rendered page onto a canvas with this much bleed on
# every side, then trims back to the trim size. Confirmed by measuring a
# rendered preview: a 6x4 card comes back as a 6.25x4.25 PDF page.
BLEED_IN = 0.125


def load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        if default is None:
            sys.exit("ERROR: {} not found".format(path))
        return default
    except json.JSONDecodeError as e:
        sys.exit("ERROR: {} is not valid JSON: {}".format(path, e))


def list_images(directory):
    if not os.path.isdir(directory):
        sys.exit("ERROR: image directory '{}' does not exist".format(directory))
    names = [f for f in os.listdir(directory) if f.lower().endswith(IMAGE_EXTS)]
    return sorted(names)


def pick_next(images, last_sent):
    """Return the first image sorting after last_sent, or None when exhausted.

    Comparing by name (rather than by a stored index) means adding or removing
    files in the folder never reshuffles what comes next.
    """
    if not images:
        return None
    if not last_sent:
        return images[0]
    for name in images:
        if name > last_sent:
            return name
    return None


def image_src(config, filename):
    """Build the src= value for the <img>: a public URL or a base64 data URI."""
    directory = config.get("image_dir", "weekly_mail_meme")
    if config.get("image_source", "url") == "base64":
        with open(os.path.join(directory, filename), "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        ext = os.path.splitext(filename)[1].lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"
        return "data:{};base64,{}".format(mime, data)

    base = config.get("image_base_url") or os.environ.get("IMAGE_BASE_URL", "")
    if not base:
        repo = os.environ.get("GITHUB_REPOSITORY")
        sha = os.environ.get("GITHUB_SHA")
        if not repo or not sha:
            sys.exit(
                "ERROR: cannot build an image URL. Set image_base_url in "
                "{}, set IMAGE_BASE_URL, or use image_source "
                '"base64".'.format(CONFIG_PATH)
            )
        base = "https://raw.githubusercontent.com/{}/{}/{}".format(
            repo, sha, directory)
    return "{}/{}".format(base.rstrip("/"), urllib.parse.quote(filename))


def escape(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def render(template, **fields):
    for key, value in fields.items():
        template = template.replace("__{}__".format(key), str(value))
    return template


FRONT_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@page { size: __W__in __H__in; margin: 0; }
html, body { margin: 0; padding: 0; width: __W__in; height: __H__in;
             overflow: hidden; background: #000000; }
/* PostGrid renders this page onto a 0.125in bleed canvas and then trims back
   to the trim size, so only the middle __VW__% x __VH__% of what we lay out
   actually survives on the card. A plain full-bleed image therefore loses its
   outer edge - which is where the speech bubbles tend to sit.
   So: .bleed only fills the border that gets cut away, and .card holds the
   whole meme inside the surviving area. object-fit:fill stretches .card to a
   __VW__%/__VH__% box, and the page scaling that follows stretches it back by
   exactly the inverse, so the printed image is undistorted. */
.bleed { position: absolute; left: 0; top: 0; width: 100%; height: 100%;
         object-fit: cover; display: block; }
.card  { position: absolute; left: __LX__%; top: __TY__%;
         width: __VW__%; height: __VH__%; object-fit: fill; display: block; }
</style></head>
<body><img class="bleed" src="__IMG__"><img class="card" src="__IMG__"></body></html>
"""

BACK_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@page { size: __W__in __H__in; margin: 0; }
html, body { margin: 0; padding: 0; width: __W__in; height: __H__in;
             background: #ffffff; }
/* Right side and bottom strip stay empty for the address block + barcode. */
.art { position: absolute; top: __M__in; left: __M__in;
       width: __IW__in; height: __IH__in; object-fit: cover; display: block; }
.caption { position: absolute; left: __M__in; top: __CT__in; width: __IW__in;
           font-family: Helvetica, Arial, sans-serif; font-size: 9pt;
           line-height: 1.25; color: #222222; }
</style></head>
<body>__BODY__</body></html>
"""


def build_html(config, src):
    size = config.get("size", "6x4")
    if size not in SIZES:
        sys.exit("ERROR: size must be one of {} (got '{}')".format(
            ", ".join(SIZES), size))
    width, height = SIZES[size]

    # Fraction of the laid-out page that survives the bleed trim.
    visible_w = width / (width + 2 * BLEED_IN)
    visible_h = height / (height + 2 * BLEED_IN)
    front = render(
        FRONT_TEMPLATE, W=width, H=height, IMG=src,
        VW=round(visible_w * 100, 4), VH=round(visible_h * 100, 4),
        LX=round((1 - visible_w) / 2 * 100, 4),
        TY=round((1 - visible_h) / 2 * 100, 4),
    )

    mode = config.get("back_mode", "image")
    text = escape(config.get("back_text", "") or "")
    art_w = round(width * ART_WIDTH_FRAC - MARGIN_IN, 3)
    art_h = round(height - MARGIN_IN - BOTTOM_CLEAR_IN, 3)
    caption_top = MARGIN_IN

    if mode == "image":
        body = '<img class="art" src="{}">'.format(src)
        caption_top = round(MARGIN_IN + art_h + 0.06, 3)
        if text:
            body += '<div class="caption">{}</div>'.format(text)
    elif mode == "text":
        body = '<div class="caption">{}</div>'.format(text) if text else ""
    elif mode == "blank":
        body = ""
    else:
        sys.exit("ERROR: back_mode must be image, text, or blank "
                 "(got '{}')".format(mode))

    back = render(BACK_TEMPLATE, W=width, H=height, M=MARGIN_IN,
                  IW=art_w, IH=art_h, CT=caption_top, BODY=body)
    return front, back


def clean_address(addr, label, source):
    if not isinstance(addr, dict):
        sys.exit("ERROR: '{}' from {} must be a JSON object".format(
            label, source))
    cleaned = {k: v for k, v in addr.items() if v not in (None, "")}
    for field in ("addressLine1", "city", "provinceOrState", "postalOrZip",
                  "countryCode"):
        if field not in cleaned:
            sys.exit("ERROR: '{}.{}' is required (from {})".format(
                label, field, source))
    return cleaned


def load_address(config, key):
    """Read an address from POSTCARD_TO / POSTCARD_FROM, else from the config.

    Real addresses live in GitHub Secrets, never in the committed config;
    this repo is public. The config block holds placeholders so that dry runs
    still work with no secrets set.
    """
    env_name = "POSTCARD_" + key.upper()
    raw = (os.environ.get(env_name) or "").strip()
    if raw:
        try:
            addr = json.loads(raw)
        except json.JSONDecodeError as e:
            sys.exit("ERROR: {} is not valid JSON: {}".format(env_name, e))
        source = env_name
    else:
        addr = config.get(key, {})
        source = CONFIG_PATH + " (placeholder)"
    return clean_address(addr, key, source), source


def redact(addr):
    """Addresses must never reach a log; this repo's Actions logs are public."""
    return {key: "***" for key in addr}


def post_postcard(payload, api_key, idempotency_key):
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
            # PostGrid sits behind Cloudflare, which rejects the default
            # "Python-urllib/x.y" agent with a 403 (error code 1010). Any
            # identifiable agent gets through.
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        sys.exit("ERROR: PostGrid returned HTTP {}\n{}".format(e.code, body))
    except urllib.error.URLError as e:
        sys.exit("ERROR: could not reach PostGrid: {}".format(e.reason))


def summary(line):
    """Surface a note on the workflow run's summary page, if we're in Actions."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def main():
    parser = argparse.ArgumentParser(description="Mail the next weekly meme "
                                                 "postcard via PostGrid.")
    parser.add_argument("--dry-run", action="store_true",
                        help="build the request and print it without sending")
    parser.add_argument("--image", help="send this filename as a one-off "
                                        "instead of the next one in the "
                                        "rotation; leaves the rotation "
                                        "pointer unchanged")
    parser.add_argument("--show-addresses", action="store_true",
                        help="show full addresses in --dry-run output; use "
                             "locally only, never in CI logs")
    args = parser.parse_args()

    config = load_json(CONFIG_PATH)
    state = load_json(STATE_PATH, default={})

    if not config.get("enabled", True):
        print("Postcard sending is disabled in postcard_config.json; skipping.")
        return 0

    directory = config.get("image_dir", "weekly_mail_meme")
    images = list_images(directory)
    print("{} image(s) in {}/".format(len(images), directory))

    if args.image:
        if args.image not in images:
            sys.exit("ERROR: '{}' not found in {}/".format(args.image, directory))
        chosen = args.image
    else:
        chosen = pick_next(images, state.get("last_sent"))

    if not chosen:
        message = ("No unsent images left in {}/ (last sent: {}). "
                   "Add more images to keep the weekly postcard going."
                   .format(directory, state.get("last_sent")))
        print("WARNING: " + message)
        summary("### :warning: Weekly postcard not sent\n\n" + message)
        return 2

    remaining = sum(1 for name in images if name > chosen)
    print("Selected: {} ({} remaining after this one)".format(chosen, remaining))

    src = image_src(config, chosen)
    front, back = build_html(config, src)

    to_addr, to_source = load_address(config, "to")
    from_addr, from_source = load_address(config, "from")
    print("Recipient from: {}\nReturn address from: {}".format(
        to_source, from_source))
    if not args.dry_run:
        for label, source in (("to", to_source), ("from", from_source)):
            if source.startswith(CONFIG_PATH):
                print("WARNING: '{}' is still the committed placeholder "
                      "address. Set the POSTCARD_{} secret before mailing "
                      "for real.".format(label, label.upper()))

    payload = {
        "to": to_addr,
        "from": from_addr,
        "frontHTML": front,
        "backHTML": back,
        "size": config.get("size", "6x4"),
        "description": "{} - {}".format(
            config.get("description", "Weekly meme postcard"), chosen),
    }

    if args.dry_run:
        printable = dict(payload)
        if config.get("image_source", "url") == "base64":
            printable["frontHTML"] = "<base64 image HTML omitted>"
            printable["backHTML"] = "<base64 image HTML omitted>"
        if not args.show_addresses:
            printable["to"] = redact(payload["to"])
            printable["from"] = redact(payload["from"])
        print("\n--- DRY RUN: request that would be POSTed ---")
        print(json.dumps(printable, indent=2))
        if not args.show_addresses:
            print("\nAddresses redacted. Pass --show-addresses to reveal them "
                  "(do this locally only - Actions logs on a public repo are "
                  "world-readable).")
        preview = src[:120] + ("..." if len(src) > 120 else "")
        print("\nImage src: " + preview)
        return 0

    api_key = os.environ.get("POSTGRID_API_KEY")
    if not api_key:
        sys.exit("ERROR: POSTGRID_API_KEY is not set")

    result = post_postcard(payload, api_key, "weekly-postcard-" + chosen)
    postcard_id = result.get("id", "unknown")
    print("Postcard created: {} (status: {})".format(
        postcard_id, result.get("status")))

    # A manual --image send is a one-off, so it leaves the weekly rotation
    # pointer alone; next week still picks up where the schedule left off.
    if args.image:
        print("Manual override: rotation state left unchanged.")
        summary("Mailed **{}** as postcard `{}` (manual override; rotation "
                "unchanged).".format(chosen, postcard_id))
        return 0

    with open(STATE_PATH, "w") as f:
        json.dump({
            "last_sent": chosen,
            "sent_date": date.today().isoformat(),
            "postcard_id": postcard_id,
            "count_sent": state.get("count_sent", 0) + 1,
        }, f, indent=2)

    summary("Mailed **{}** as postcard `{}`. {} image(s) remaining.".format(
        chosen, postcard_id, remaining))
    return 0


if __name__ == "__main__":
    sys.exit(main())
