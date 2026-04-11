# MSHSAA Setup Guide

## Goal

AthletiSync treats MSHSAA as the source of truth. The district updates schedules in MSHSAA, and AthletiSync reads those schedules and publishes them to Google Calendar destinations defined by mappings.

## What You Need

- One MSHSAA school page URL for each school you want to sync
- The school year you want to publish
- A list of sports and levels you expect to expose

## How To Find The Correct MSHSAA URL

1. Open the school's page on the MSHSAA website in your browser.
2. Copy the school home page URL from the address bar.
3. Use the full URL in AthletiSync, typically in this format:

```text
https://www.mshsaa.org/MySchool/?s=244
```

4. Do not worry about extracting the numeric school ID separately for the MVP UI.
5. In AthletiSync, paste that URL into the `MSHSAA URL` field and click `Preview Source`.

AthletiSync can derive the linked schedule page from the school home page when needed.

## Current MVP Workflow

1. Go to `Schools` in AthletiSync.
2. Create a school record.
3. Paste the MSHSAA school page URL into the `MSHSAA URL` field.
4. Click `Preview Source`.
5. Confirm that AthletiSync can load activities from the page.
6. Add or confirm the needed school years, sports, and levels.
7. Create sync mappings to Google Calendar destinations.

## What Preview Source Does

The preview action fetches the configured MSHSAA school page and parses the activity selector that MSHSAA exposes. This gives you a fast validation step before relying on the school record for live sync work.

Use this to catch:

- incorrect school page URLs
- district pages that require a different source URL pattern
- provider markup changes that break parsing

## Recommended Data Entry Pattern

- One school record per actual school
- One MSHSAA URL per school record
- Separate mappings for each school year, sport, and level combination you plan to publish
- Ignore MSHSAA numeric school IDs in the UI for now unless a future integration step explicitly asks for them

## Source Notes

- MSHSAA markup can change over time, so source parsing is intentionally isolated in `app/integrations/mshsaa.py`.
- The current MVP validates school pages and activity discovery first.
- Full district-specific live schedule ingestion should be verified against your actual school pages before production use.

## Troubleshooting

If `Preview Source` fails:

- confirm the MSHSAA URL loads in a browser
- confirm it is a school-level athletics page and not a generic landing page
- check whether the activity selector is rendered directly in the HTML
- review application logs for parser or network errors
