# Google Calendar Setup Guide

## Recommended MVP Approach

Use a Google service account with access delegated to the destination calendars.

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
