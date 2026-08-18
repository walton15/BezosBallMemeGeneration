# BezosBallMemeGeneration

Automatically generates and emails a daily AI-generated meme to a friend on weekdays, at a random time between 6:15pm and 9:00pm EDT.

## How it works

1. GitHub Actions runs Monday–Friday at 5:30pm EDT
2. GPT-4o generates a random scene/style description (medieval, anime, space, etc.),
   themed around the holiday if the day happens to be one
3. DALL-E 3 renders the meme with the dialogue baked in
4. The image is committed to the repo as `meme.jpg`
5. The same job picks a **random send time between 6:15pm and 9:00pm ET** and records it in `next_send.json`
6. A second workflow (`email_meme.yml`) wakes up every 15 min during the window; once the chosen time has passed it emails `meme.jpg` to Evan (respecting `send_today.json`), marks it sent, and stops
7. (Optional) An iOS Shortcut can also fetch the image and text it to your friend

The random time is stored in `next_send.json`, so no runner sits idle waiting — the poller only runs ~15 seconds per check. Send time is quantized to the next 15-min tick.

## Meme format

Every meme has the same dialogue in a different visual style and setting:
- Aggressor: **"GET OUT OF THE BALLS EVAN"**
- Victim: **"MY PRODUCTIVITY"**

## Repository structure

```
.github/
  workflows/
    daily_meme.yml       — runs Mon-Fri at 5:30pm EDT: generates meme.jpg + picks the send time
    email_meme.yml       — polls every 15 min in the window, emails meme.jpg once the time passes
    manage_schedule.yml  — manually enable/disable sending by date range
    weekly_postcard.yml  — runs Mondays 9am ET: mails the next meme as a postcard
    generate_weekly_memes.yml — manual: fills weekly_mail_meme/ with the year's images
generate_meme.py         — calls GPT-4o + DALL-E 3, writes meme.jpg and send_today.json
schedule_email.py        — picks a random 6:15–9:00pm ET send time, writes next_send.json
email_gate.py            — decides whether email_meme.yml should send on the current tick
update_config.py         — updates config.json for enable/disable actions
send_weekly_postcard.py  — picks the next weekly image and mails it via PostGrid
generate_weekly_memes.py — generates a year of postcard memes, holiday-aware
holiday_theme.py         — shared holiday calendar used by both meme paths
fetch_postcard_preview.py — downloads a rendered postcard PDF to check the print
config.json              — stores disabled date ranges + evan_substitution_chance
art_styles.txt           — 1000 art styles; one is picked at random per meme
scenes.txt               — 1000 scene setups; one is picked at random per meme
evan_images/             — real photos of Evan; occasionally composited in (see below)
send_today.json          — whether sending is enabled today (true/false)
next_send.json           — today's randomly-chosen send time + sent flag
meme.jpg                 — the latest generated meme (overwritten daily)
postcard_config.json     — postcard recipient/return address, size, back layout
weekly_postcard_state.json — which image the postcard rotation last mailed
weekly_mail_meme/        — 52 postcard memes, one per week, mailed in name order
```

## Setup

### 1. Secrets
Add these repository secrets (Repo → Settings → Secrets and variables → Actions → New repository secret):

| Name | Value |
|------|-------|
| `OPENAI_API_KEY` | Your OpenAI API key (used to generate the meme) |
| `MAIL_USERNAME` | The Gmail address the meme is sent **from** |
| `MAIL_PASSWORD` | A Gmail [App Password](https://myaccount.google.com/apppasswords) for that account (not your normal password; requires 2FA enabled) |
| `POSTGRID_API_KEY` | PostGrid Print & Mail API key, for the weekly postcard (`test_sk_...` to rehearse, `live_sk_...` to actually mail) |
| `POSTCARD_TO` | Postcard recipient address as a JSON object (kept out of this public repo) |
| `POSTCARD_FROM` | Postcard return address as a JSON object |

The email is sent **to** `evanlazaro@gmail.com` (change the `to:` field in `email_meme.yml` to send elsewhere).

### 2. Test the workflow
- Actions tab → Daily Meme Generator → Run workflow → main

### 3. iOS Shortcut
Create a Shortcut with these actions:

| Step | Action | Value |
|------|--------|-------|
| 1 | Get Contents of URL | `https://raw.githubusercontent.com/walton15/BezosBallMemeGeneration/main/send_today.json` |
| 2 | Get Dictionary from Input | (result of step 1) |
| 3 | Get Dictionary Value | key: `send` |
| 4 | If value is `0` | Stop and Output (empty) |
| 5 | Otherwise | (end if block) |
| 6 | Get Contents of URL | `https://raw.githubusercontent.com/walton15/BezosBallMemeGeneration/main/meme.jpg` |
| 7 | Send Message | Message: result of step 6, Recipient: your friend |

Then create a Personal Automation: Time of Day → 9:15pm → Mon–Fri → run the shortcut → disable "Ask Before Running".

## Real-person substitution

On each run there's a configurable chance to swap the generated "inside the
ball" victim for a real photo of Evan:

1. Put photos (`.png`/`.jpg`/`.jpeg`/`.webp`) in `evan_images/`.
2. Set the odds in `config.json` via `evan_substitution_chance` (default `0.05` = 5%).

When it triggers, a random photo is picked and composited into the scene via the
OpenAI image **edit** endpoint (preserving the real face). If the roll fails, or
`evan_images/` is empty/missing, a normal fully-generated meme is produced.

## Disabling for a date range

Go to **Actions → Manage Schedule → Run workflow**, then:
- Action: `disable`
- Start date: `YYYY-MM-DD`
- End date: `YYYY-MM-DD`

To re-enable early, run it again with action: `enable`.

The workflow updates `config.json`. The next time the daily workflow runs, it will write `send: false` to `send_today.json` and the Shortcut will skip sending.

**Note:** Disable before 5:30pm EDT on the day you want to skip. If the daily workflow has already run and picked a send time, disabling still works — `email_gate.py` re-checks `send_today.json` on every tick, so `send: false` stops that day's email.

## Weekly physical postcard

Every **Monday at 9:00am ET**, `weekly_postcard.yml` mails one image from
`weekly_mail_meme/` as a real postcard via the [PostGrid](https://www.postgrid.com/)
Print & Mail API.

### Picking the image

`weekly_mail_meme/` holds a year of images, generated ahead of time by
`generate_weekly_memes.py` (see below). Each run mails the **next one in
ascending filename order**:

```
weekly_mail_meme/
  week_01.jpg               <- mailed first
  week_02_labor_day.jpg     <- holiday weeks say so in the name
  week_03.jpg
  ...
```

Holiday suffixes do not disturb the order: `week_10_halloween.jpg` sorts
between `week_09.jpg` and `week_11.jpg`.

`weekly_postcard_state.json` records the filename that was last mailed, and the
next run picks the first name sorting after it. Because the pointer is a
**filename, not an index**, adding or deleting files never reshuffles what comes
next — new images just need names that sort after the last one sent.

When the queue runs out the workflow **fails on purpose** (exit code 2) so GitHub
emails you the red X. Top up `weekly_mail_meme/` and the next run resumes.

### Generating the year's images

`generate_weekly_memes.py` fills the queue in one go. It maps 52 mailing Mondays
starting from the next Monday, themes the weeks that line up with a holiday, and
writes `1536x1024` JPEGs — exactly 3:2, the 6x4 postcard aspect, so nothing is
cropped when the front is printed full-bleed.

```bash
python generate_weekly_memes.py --list       # free: print the plan, no API calls
python generate_weekly_memes.py --limit 2    # generate the first two
python generate_weekly_memes.py              # generate all remaining weeks
```

Run it in CI via **Actions -> Generate Weekly Memes**, where `OPENAI_API_KEY`
already lives. Inputs: `limit`, `start_week`, and `force` (regenerate weeks that
already have an image).

The run is **resumable** — a week whose file already exists is skipped, and the
workflow commits images even if the job fails partway, so a crash never means
paying for the same image twice. Individual failures are collected and reported
at the end instead of aborting the batch; re-running retries only what's missing.

### Holidays

`holiday_theme.py` holds one holiday calendar shared by **both** meme paths, so
adding a date themes the daily email meme and the weekly postcard at once.

The two use different timing, because they are delivered differently:

| | When it themes |
|---|---|
| **Daily meme** | On the holiday itself. Emailed the same evening it's generated. The daily workflow only runs Mon-Fri, so a **weekend** holiday themes the **Friday before** — otherwise Halloween on a Saturday would never be themed. |
| **Weekly postcard** | The week containing the holiday, or the **week before** when it falls on a **Monday or Tuesday**, since a card mailed Monday arrives days later. Every themed card mails 2-13 days ahead. |

17 of the 52 postcard weeks are themed. Entries are scored by priority, so when
two land together the bigger one wins — Valentine's beats Presidents' Day,
Cinco de Mayo beats Mother's Day. **Evan's birthday (August 1)** outranks
everything.

Add, remove, or re-rank dates in `holidays_in()` in `holiday_theme.py`, and give
each slug a human-readable name in `HOLIDAY_LABELS` — that label is what the
prompt model is told to theme around.

### Configuration

Everything mailing-related lives in `postcard_config.json`:

| Key | Meaning |
|-----|---------|
| `enabled` | Set `false` to pause mailing without touching the schedule |
| `size` | `6x4`, `9x6`, or `11x6` |
| `image_dir` | Folder holding the queue (default `weekly_mail_meme`) |
| `image_source` | `url` (default) or `base64` — see below |
| `image_base_url` | Optional; overrides the auto-derived image URL |
| `back_mode` | `blank` (default: addresses only), `image`, or `text` |
| `back_text` | Caption printed on the back (used by `image` and `text`) |
| `to` / `from` | Placeholder addresses only; real ones come from secrets (see below) |

### Addresses live in secrets, not in the repo

**This repo is public, so real street addresses are never committed to it.** The
`to`/`from` blocks in `postcard_config.json` are permanent placeholders. Real
addresses come from two repository secrets, each holding a JSON object:

| Secret | Meaning |
|--------|---------|
| `POSTCARD_TO` | Recipient address |
| `POSTCARD_FROM` | Return address (required by the carrier) |

```bash
gh secret set POSTCARD_TO --body '{"firstName":"Jane","lastName":"Doe","addressLine1":"123 EXAMPLE ST UNIT 1A","city":"SEATTLE","provinceOrState":"WA","postalOrZip":"98101","countryCode":"US"}'
```

`addressLine1`, `city`, `provinceOrState`, `postalOrZip`, and `countryCode` are
required; the script fails fast if any is missing, and it names the source it
used (`POSTCARD_TO` vs. the placeholder file) on every run.

To change the recipient later, update the secret — no commit required.

**Addresses are redacted from script output by default**, because Actions logs on
a public repo are world-readable. Pass `--show-addresses` to reveal them in a
local `--dry-run`. A real send still falling back to the committed placeholders
prints a loud warning.

### How the image reaches PostGrid

PostGrid renders an HTML string per side rather than accepting a file upload, so
the JPG has to be fetchable by URL. With `image_source: "url"` the script builds
a `raw.githubusercontent.com` link pinned to the **current commit SHA**, so
PostGrid always prints the exact committed bytes. This relies on the repo being
public.

If you ever make the repo private, set `image_source: "base64"` and the image is
inlined as a data URI instead — no public URL needed.

### Bleed and trim

PostGrid composites the rendered page onto a canvas with **0.125in of bleed on
every side**, then trims back to the trim size. A 6x4 card comes back as a
6.25x4.25 PDF page — measured from a real rendered preview, not assumed.

A naive full-bleed image therefore loses its outer edge, which is exactly where
speech bubbles tend to sit; the first test render clipped one. So the front lays
the meme into only the area that survives the trim, with a cover copy behind it
filling the border that gets cut away. `object-fit: fill` on the inner copy and
the page scaling that follows cancel out, so the print is undistorted.

This is why `BLEED_IN` exists in `send_weekly_postcard.py`. If PostGrid ever
changes that margin, a preview will show it and only that constant needs editing.

### The address side

`back_mode` is `"blank"`: a plain white side carrying just the return address and
the recipient, which is what PostGrid overlays itself. `"image"` puts art on the
left (clear of the address block and the USPS barcode strip) and `"text"` prints
`back_text` there. Printing the back costs nothing extra either way, since the
address is printed there regardless.

### Setup

1. Create a PostGrid account and grab an API key from the dashboard.
2. Add it as repository secret `POSTGRID_API_KEY`.
   - `test_sk_...` keys render the postcard and cost nothing but **mail nothing** — use one to verify.
   - `live_sk_...` keys mail for real and bill your account.
3. Set the `POSTCARD_TO` and `POSTCARD_FROM` secrets (see above). Do **not**
   put real addresses in `postcard_config.json`.
4. Actions -> Weekly Meme Postcard -> Run workflow, with **dry run** checked.

### Manual runs

Actions -> **Weekly Meme Postcard** -> Run workflow:

- **dry run** — builds and prints the exact request without contacting PostGrid.
- **image** — mails a specific filename as a one-off. This deliberately leaves
  the rotation pointer alone, so the weekly sequence continues undisturbed.

Locally:

```bash
# Placeholder addresses, output redacted
python send_weekly_postcard.py --dry-run

# Real address from env, revealed locally so you can eyeball it
POSTCARD_TO="$(cat ~/postcard_to.json)" \n  python send_weekly_postcard.py --dry-run --show-addresses
```

Each send uses an `Idempotency-Key` derived from the **request content**, so an
identical retry (a re-run of the same Monday) will not mail a duplicate, while a
genuinely different card — new layout, new address — still goes through. Keying on
the filename alone would silently return the previously rendered card.

### Checking how a card actually prints

```bash
$env:POSTGRID_API_KEY = "test_sk_..."      # PowerShell; use export in bash
python fetch_postcard_preview.py           # list recent postcards
python fetch_postcard_preview.py postcard_1e5W851CsfBG5pGuHzGnDv
```

Saves `previews/<id>.pdf` (gitignored). Deliberately **local-only**: the rendered
back shows the recipient's address, and this repo's Actions logs are public.

With a `test_sk_` key a postcard renders fully and mails nothing, so this is the
free way to check layout before spending anything.

**Note:** PostGrid sits behind Cloudflare, which rejects Python's default
`Python-urllib/x.y` User-Agent with a 403 (error code 1010) before the request
reaches the API. `send_weekly_postcard.py` sends an explicit `User-Agent`; keep it
if you rewrite the request code.

### Cost

PostGrid charges **$0.902** per 6x4 postcard, US First Class, which *includes
printing, processing and postage*. At one per week that is about **$3.90/month**
or **$46.90/year**. No platform fee applies: the Starter tier covers up to 500
mailings/month at $0 and this uses roughly four.

US Standard Class is cheaper but PostGrid only offers it at 6x9 and 6x11, and it
is built for bulk, so First Class is the rate for a weekly single. Printing the
back costs nothing either way.

Test-mode (`test_sk_`) postcards render fully and bill nothing.

Generating the year's 52 images is a **one-off** cost: gpt-image-2 at medium
quality runs roughly $0.04-0.05 per 1536x1024 image, plus a GPT-4o prompt call
each, so about **$3** total. Verify against your own OpenAI usage dashboard -
image pricing is billed per-token and changes.

## Timezone note

The **send time** (6:15–9:00pm) is computed in `America/New_York` by `schedule_email.py` / `email_gate.py`, so it follows DST automatically — no seasonal edits needed. `email_meme.yml`'s poll cron already spans the UTC hours for both EDT and EST.

Only the **generation** trigger in `daily_meme.yml` is a fixed UTC cron (`30 21 * * 1-5` = 5:30pm EDT / 4:30pm EST). Either way it runs before the send window, so no seasonal edit is required there either.

## Cost

The daily meme costs two OpenAI calls per weekday: GPT-4o writes the prompt, then
`gpt-image-2` renders it at 1024x1024, `quality="medium"`. That works out to very
roughly **$0.80/month** over ~20 weekdays. Emailing itself is free (Gmail SMTP),
as are Actions minutes on a public repo. Check your OpenAI usage dashboard for
actual spend — image generation is billed per-token.

Lower `quality` in `generate_meme.py` to cut this; the postcards are a separate
code path and keep their resolution.
