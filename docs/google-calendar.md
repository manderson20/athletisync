# Google Calendar Setup Guide

## Recommended Approach

Use Google OAuth with the dedicated Google account that already manages the destination calendars.

## Google OAuth Setup

1. In Google Cloud, create or choose a project.
2. Enable the Google Calendar API.
3. Create an OAuth client for a web application.
4. Add the AthletiSync callback URL as an authorized redirect URI.
5. In AthletiSync, open `Settings` and set `Server Base URL` to the URL users use to reach that deployment, such as `http://172.16.1.77` or `https://athletics.yourschool.edu`.
6. In AthletiSync, open the `Google` page and enter these values in the `Google OAuth Configuration` section:

- `Google OAuth Client ID`
- `Google OAuth Client Secret`
- `Google OAuth Redirect URI`

7. Save the Google OAuth configuration on that page.
8. In the Google page inside AthletiSync, use `Connect Google Account`.
9. Sign in with the dedicated Google account that already has edit access to the calendars.
10. After the profile is saved, add a calendar destination record with the calendar's `Calendar ID` and the connected auth profile.
11. Use the calendar access test button in the UI to confirm the connected account has `writer` or `owner` access.

## Optional Environment Fallback

If you prefer, the same OAuth client values can still be supplied through `.env` as a fallback:

```env
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=https://your-server/google/oauth/callback
```

## Mapping Examples

- All athletics in one calendar: point every mapping to the same calendar record.
- One calendar per sport: create one calendar record per sport and map accordingly.
- One calendar per school: create one destination per school.
- One calendar per school + sport + level: create granular destination records and map each combination individually.
