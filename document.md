# BezosBallMemeGeneration

Automatically generates and emails a daily AI-generated meme to a friend on weekdays, at a random time between 6:15pm and 9:00pm EDT.

## How it works

1. GitHub Actions runs Monday–Friday at 5:30pm EDT
2. GPT-4o generates a random scene/style description (medieval, anime, space, etc.)
3. DALL-E 3 renders the meme with the dialogue baked in
4. The image is committed to the repo as `meme.jpg`
5. A second GitHub Actions workflow fires at 6:15pm EDT, waits a random 0–165 min, then emails `meme.jpg` to Evan (respecting `send_today.json`) — so the send lands somewhere between 6:15pm and 9:00pm EDT
6. (Optional) An iOS Shortcut can also fetch the image and text it to your friend

## Meme format

Every meme has the same dialogue in a different visual style and setting:
- Aggressor: **"GET OUT OF THE BALLS EVAN"**
- Victim: **"MY PRODUCTIVITY"**

## Repository structure

```
.github/
  workflows/
    daily_meme.yml       — runs Mon-Fri at 5:30pm EDT, generates and commits meme.jpg
    email_meme.yml       — fires Mon-Fri at 6:15pm EDT, random 0–165 min delay, emails meme.jpg (gated on send_today.json)
    manage_schedule.yml  — manually enable/disable sending by date range
generate_meme.py         — calls GPT-4o + DALL-E 3, writes meme.jpg and send_today.json
update_config.py         — updates config.json for enable/disable actions
config.json              — stores disabled date ranges + evan_substitution_chance
art_styles.txt           — 1000 art styles; one is picked at random per meme
scenes.txt               — 1000 scene setups; one is picked at random per meme
evan_images/             — real photos of Evan; occasionally composited in (see below)
send_today.json          — tells the iOS Shortcut whether to send today (true/false)
meme.jpg                 — the latest generated meme (overwritten daily)
```

## Setup

### 1. Secrets
Add these repository secrets (Repo → Settings → Secrets and variables → Actions → New repository secret):

| Name | Value |
|------|-------|
| `OPENAI_API_KEY` | Your OpenAI API key (used to generate the meme) |
| `MAIL_USERNAME` | The Gmail address the meme is sent **from** |
| `MAIL_PASSWORD` | A Gmail [App Password](https://myaccount.google.com/apppasswords) for that account (not your normal password; requires 2FA enabled) |

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

**Note:** Disable before 9pm EDT on the day you want to skip. If the daily workflow has already run, it's too late to stop that day's send.

## Timezone note

The workflow crons are set for EDT (UTC-4). When clocks fall back in November (EST, UTC-5), update both `daily_meme.yml` and `email_meme.yml`:

```
# daily_meme.yml  — EDT (summer): '30 21 * * 1-5'  EST (winter): '30 22 * * 1-5'
# email_meme.yml  — EDT (summer): '15 22 * * 1-5'  EST (winter): '15 23 * * 1-5'
```

## Cost

~$0.04/image × ~20 weekdays/month = **~$0.80/month** (OpenAI DALL-E 3 standard quality)
