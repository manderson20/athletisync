# Google Calendar Setup Guide

## Recommended Approach

Use Google OAuth with the dedicated Google account that already manages the destination calendars.

## Google OAuth Setup

1. In Google Cloud, create or choose a project.
2. Enable the Google Calendar API.
3. Create an OAuth client for a web application.
4. Add the AthletiSync callback URL as an authorized redirect URI.
5. In AthletiSync, open `Settings` and enter these values in the `Google OAuth` section:

- `Google OAuth Client ID`
- `Google OAuth Client Secret`
- `Google OAuth Redirect URI`

6. Save settings.
7. In the Google page inside AthletiSync, use `Connect Google Account`.
8. Sign in with the dedicated Google account that already has edit access to the calendars.
9. After the profile is saved, add a calendar destination record with the calendar's `Calendar ID` and the connected auth profile.
10. Use the calendar access test button in the UI to confirm the connected account has `writer` or `owner` access.

## Optional Environment Fallback

If you prefer, the same OAuth client values can still be supplied through `.env` as a fallback:

```env
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=https://your-server/google/oauth/callback
```

## Legacy Service Account Setup

Use this only if the service account can actually be granted edit access to the destination calendars.

## Steps

1. Create a Google Cloud project.
2. Enable the Google Calendar API.
3. Create a service account and generate a JSON key.
4. Share the target calendar with the service account email.
5. Install AthletiSync with the Google integration extra:

```bash
pip install -e ".[dev,google]"
```

6. Paste the service account JSON into the Google auth profile form.
7. Add one or more Google calendar destination records.
8. Use the profile connection test button in the UI.

## Mapping Examples

- All athletics in one calendar: point every mapping to the same calendar record.
- One calendar per sport: create one calendar record per sport and map accordingly.
- One calendar per school: create one destination per school.
- One calendar per school + sport + level: create granular destination records and map each combination individually.
