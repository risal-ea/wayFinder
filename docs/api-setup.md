# API Setup: Wikivoyage

How to access Wikivoyage, WayFinder's destination data source, and configure the backend to use it. For what the data is used for, see [wikivoyage-plan.md](wikivoyage-plan.md).

Access rules and limits below were checked against the live service in November 2026.

| | Wikivoyage |
|---|---|
| Needs an account? | **No** |
| What you configure | `WIKIVOYAGE_CONTACT` (goes into the User-Agent) |
| Limits | 200 requests/min with a proper User-Agent, ≤ 3 concurrent |
| Licence | CC BY-SA 4.0, attribution required |

> OpenTripMap was the planned second source but was dropped (Nov 2026) because an account couldn't be created. If a second source is needed later, the fallback in [destination-data-plan.md](destination-data-plan.md) (Overpass + Wikidata, no key) is the first candidate.

## 1. No key, but a User-Agent is mandatory
Wikimedia blocks requests that have no User-Agent or a generic one. Tested against `en.wikivoyage.org/w/api.php`:

| User-Agent sent | Result |
|---|---|
| none | 403 |
| `python-requests/2.31.0` (library default) | 403 |
| `Python-urllib/3.12` | 403 |
| `WayFinder/0.1 (https://…; you@example.com)` | 200 |

The format required by the [Wikimedia User-Agent policy](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy) is:

```
<client>/<version> (<contact URL or email>) <library>/<version>
```

The backend builds it for you from `.env`:
```
WayFinder/0.1.0 (https://github.com/risal-ea/wayFinder; you@example.com) httpx/0.28.1
```

The contact must be real. Wikimedia uses it to reach you before blocking a misbehaving client.

## 2. Test it
```bash
curl -s \
  -H "User-Agent: WayFinder/0.1 (https://github.com/risal-ea/wayFinder; you@example.com)" \
  "https://en.wikivoyage.org/w/api.php?action=query&prop=extracts&exintro=1&explaintext=1&titles=Kyoto&redirects=1&format=json&formatversion=2"
```
Expected: HTTP 200 with JSON starting `{"batchcomplete":true,"query":{"pages":[{"pageid":18579,…,"title":"Kyoto","extract":"Kyōto (京都) was the capital of Japan…`.

You can also import [backend/postman/WayFinder.postman_collection.json](../backend/postman/WayFinder.postman_collection.json) into Postman. It has every call the backend makes, plus the edge cases.

## 3. Rate limits (enforced since 2026)
From [Wikimedia APIs/Rate limits](https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits):

| Client type | Requests per minute |
|---|---|
| No identifiable User-Agent | 10 |
| **Anonymous, compliant User-Agent (WayFinder by default)** | **200** |
| Authenticated, new account | 200 |
| Authenticated, established editor | 2,000 |

- Keep **3 or fewer concurrent requests**. The backend uses 1, at least 200 ms apart.
- When you go over the limit you get **429** (or 503 when a backend is overloaded) with `Retry-After`. The backend honours it. If it's missing, it waits at least 5 s.
- Server lag comes back as HTTP 200 with `error.code = "maxlag"` and `Retry-After`. The backend retries it.

## 4. Optional: OAuth for higher limits
**Not needed for development.** A token only raises the limit if the account behind it is an established editor. A new account gets the same 200/min as an anonymous client. If you ever need it:

1. Propose an OAuth 2 consumer at https://meta.wikimedia.org/wiki/Special:OAuthConsumerRegistration/propose/oauth2 and choose the **Client credentials** flow. You receive a client ID and a secret.
2. Exchange them for a token (valid for 4 hours):
   ```bash
   curl -s -X POST https://meta.wikimedia.org/w/rest.php/oauth2/access_token \
     -d grant_type=client_credentials \
     -d client_id=$WIKIMEDIA_CLIENT_ID \
     -d client_secret=$WIKIMEDIA_CLIENT_SECRET
   ```
3. Send `Authorization: Bearer <access_token>` on each request, together with the User-Agent.

Notes:
- The old **API Portal (api.wikimedia.org) personal tokens were retired in June 2026**. Don't follow guides that use them.
- Only apps registered on or after 2026-10-19 count as the registering user.
- The Wikivoyage endpoint does validate Bearer tokens. An end-to-end test with a real token has not been done yet.

## 5. Configure the backend
```bash
cd backend
cp .env.example .env
```

Set your contact in `backend/.env`. `.env` is git-ignored; only `.env.example` is committed.

```dotenv
WIKIVOYAGE_CONTACT=you@example.com   # required: email or URL
APP_URL=https://github.com/risal-ea/wayFinder

# Optional tuning
# WIKIVOYAGE_LANG=en
# WIKIVOYAGE_MIN_INTERVAL=0.2
# HTTP_TIMEOUT=30
```

[config.py](../backend/src/wayfinder/config.py) refuses to start if `WIKIVOYAGE_CONTACT` is missing or isn't an email address or URL.

Check that it works:
```bash
uv run pytest -m live
```

## 6. Checklist
- [ ] Real contact email/URL in `WIKIVOYAGE_CONTACT`
- [ ] The curl above returns 200, not 403
- [ ] `uv run pytest -m live` passes
- [ ] `.env` not committed
- [ ] Wikivoyage text shown with attribution (article link + CC BY-SA 4.0), kept separate from AI-generated text

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| App won't start: `wikivoyage_contact` field required | `WIKIVOYAGE_CONTACT` not set, or `.env` not found | Run from `backend/`; check `.env` |
| 403 "Please set a user-agent" | No User-Agent, or a library default one | Use the client (it sets one); in Postman, set the `user_agent` variable |
| 429 / `ProviderRateLimited` | Over 200/min or too many in parallel | Requests are serialised; slow down batch jobs, honour `retry_after` |
| `error.code = "maxlag"` | Wikimedia servers are lagging | The client retries automatically |
| Request hangs, then returns an empty body | Known intermittent behaviour | The client times out after 30 s and retries |
| `PageNotFound` | Title doesn't exist | Use `search()` or `resolve()` first; titles are case-sensitive after the first letter |
