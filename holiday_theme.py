"""Which holiday, if any, a given date should be themed around.

Shared by both meme paths, so a holiday added here shows up in the daily email
meme and in the weekly postcard queue at once:

  - generate_meme.py       themes the day's meme when today is a holiday
  - generate_weekly_memes.py themes the postcard for the week near a holiday

The two use different timing rules, because they're delivered differently:

  Daily   the meme is emailed the same evening it's generated, so it themes on
          the holiday itself. The daily workflow only runs Mon-Fri, so a
          holiday landing on a weekend themes the Friday before it - otherwise
          Halloween on a Saturday would never be themed at all.

  Weekly  a postcard mailed Monday arrives several days later, so the themed
          card ships the week containing the holiday, or the week before when
          the holiday falls on a Monday or Tuesday. See build_schedule() in
          generate_weekly_memes.py.
"""

from datetime import date, timedelta

# Higher priority wins when two land on the same day or in the same week.
PRIORITY_BIRTHDAY = 6
PRIORITY_MAJOR = 5
PRIORITY_MEDIUM = 3
PRIORITY_MINOR = 1

HOLIDAY_LABELS = {
    "evan_birthday": "Evan's birthday",
    "new_years": "New Year's Day",
    "mlk_day": "Martin Luther King Jr. Day",
    "groundhog_day": "Groundhog Day",
    "valentines": "Valentine's Day",
    "presidents_day": "Presidents' Day",
    "pi_day": "Pi Day (March 14th, the maths/pie holiday)",
    "st_patricks": "St. Patrick's Day",
    "easter": "Easter",
    "april_fools": "April Fools' Day",
    "cinco_de_mayo": "Cinco de Mayo",
    "mothers_day": "Mother's Day",
    "memorial_day": "Memorial Day",
    "fathers_day": "Father's Day",
    "juneteenth": "Juneteenth",
    "independence": "the Fourth of July / Independence Day",
    "labor_day": "Labor Day",
    "halloween": "Halloween",
    "thanksgiving": "Thanksgiving",
    "christmas": "Christmas",
    "new_years_eve": "New Year's Eve",
}


def easter(year):
    """Anonymous Gregorian computus."""
    a = year % 19
    b, c = year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    el = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * el) // 451
    month = (h + el - 7 * m + 114) // 31
    day = ((h + el - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def nth_weekday(year, month, weekday, n):
    first = date(year, month, 1)
    first += timedelta(days=(weekday - first.weekday()) % 7)
    return first + timedelta(weeks=n - 1)


def last_weekday(year, month, weekday):
    if month == 12:
        last = date(year, 12, 31)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def holidays_in(year):
    """(slug, date, priority) for every themed day in one year."""
    return [
        ("new_years", date(year, 1, 1), PRIORITY_MAJOR),
        ("mlk_day", nth_weekday(year, 1, 0, 3), 2),
        ("groundhog_day", date(year, 2, 2), PRIORITY_MINOR),
        ("valentines", date(year, 2, 14), PRIORITY_MAJOR),
        ("presidents_day", nth_weekday(year, 2, 0, 3), 2),
        ("pi_day", date(year, 3, 14), PRIORITY_MINOR),
        ("st_patricks", date(year, 3, 17), 4),
        ("easter", easter(year), 4),
        ("april_fools", date(year, 4, 1), PRIORITY_MEDIUM),
        ("cinco_de_mayo", date(year, 5, 5), PRIORITY_MEDIUM),
        ("mothers_day", nth_weekday(year, 5, 6, 2), PRIORITY_MEDIUM),
        ("memorial_day", last_weekday(year, 5, 0), PRIORITY_MEDIUM),
        ("fathers_day", nth_weekday(year, 6, 6, 3), PRIORITY_MEDIUM),
        ("juneteenth", date(year, 6, 19), 2),
        ("independence", date(year, 7, 4), PRIORITY_MAJOR),
        # Evan's birthday outranks everything else.
        ("evan_birthday", date(year, 8, 1), PRIORITY_BIRTHDAY),
        ("labor_day", nth_weekday(year, 9, 0, 1), PRIORITY_MEDIUM),
        ("halloween", date(year, 10, 31), PRIORITY_MAJOR),
        ("thanksgiving", nth_weekday(year, 11, 3, 4), PRIORITY_MAJOR),
        ("christmas", date(year, 12, 25), PRIORITY_MAJOR),
        ("new_years_eve", date(year, 12, 31), 2),
    ]


def label_for(slug):
    """Human-readable name to hand the prompt model."""
    return HOLIDAY_LABELS.get(slug)


def observed_weekday(when):
    """The weekday a holiday is themed on for the *daily* meme.

    Weekend holidays move to the Friday before, since the daily workflow only
    runs Mon-Fri. Early beats late for a holiday greeting, so Sunday holidays
    also move back rather than forward.
    """
    if when.weekday() == 5:              # Saturday
        return when - timedelta(days=1)
    if when.weekday() == 6:              # Sunday
        return when - timedelta(days=2)
    return when


def holiday_for_date(today):
    """(slug, holiday_date) to theme today's meme around, or (None, None)."""
    best = None
    for year in (today.year, today.year + 1):
        for slug, when, priority in holidays_in(year):
            if observed_weekday(when) != today:
                continue
            if best is None or priority > best[2]:
                best = (slug, when, priority)
    if best is None:
        return None, None
    return best[0], best[1]
