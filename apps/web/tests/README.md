# Hunter regression checks

Run the request/parser tests from `apps/web`:

```powershell
node --experimental-strip-types --test tests/hunter-client.test.mjs
```

`hunter-browser-check.py` is a browser harness for the real HunterClient component,
with local API interception. It does not test production authentication or make
real searches. The September 8, 2026 run passed these scenarios:

- Display the confirmation response directly without another history request.
- Bring results into the mobile viewport without horizontal overflow.
- Show an explicit completed/empty result.
- Surface an HTML response and a connection failure as errors.
- Never disguise an invalid history response as an empty history.

To repeat that harness, expose HunterClient at `/hunter-verification` on a local
development server on port 3100, outside the authenticated app layout. Exclude
only that temporary route from Clerk middleware in development. Remove the
temporary route and middleware exclusion before building or deploying. Never
disable authentication on production routes. The harness requires Python's
Playwright and Chromium. `hunter-mobile-result.png` is the captured fixture UI,
not real customer data.
