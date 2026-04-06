"""Verification checklist template."""


def render_verify_checklist() -> str:
    """Render the verification checklist template."""
    return """# Verification Checklist

## Build
- [ ] success

## Tests
- [ ] targeted tests pass

## Mobile
- [ ] flow verified
- [ ] UI correct
- [ ] permissions correct

## Regression
- [ ] critical paths OK
"""
