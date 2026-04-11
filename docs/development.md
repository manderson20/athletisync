# Development Guide

## Code Style

- Prefer typed Python code.
- Keep integrations provider-specific and isolated.
- Add concise comments only where control flow or coupling is not obvious.
- Update `version` and `Changelog` for user-visible changes.

## Testing

```bash
pytest
```

Recommended future additions:

- route tests with `TestClient`
- live provider fixture parsing tests
- scheduler integration tests
- Google gateway contract tests
