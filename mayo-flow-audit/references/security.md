# Security dimension: active request testing (audit dimension 1)

Read in full before auditing security. Reading the code and impersonating
roles in the database is not enough: the bugs below live in how the server
treats a request an attacker has edited. For each item, **send the edited
request and record what came back**. A lead that was only read in source is
`needs validation`, not `confirmed` and not "fine".

## How to run it

- Target the local or test instance only, never production. Use throwaway or
  seed accounts. Refuse if the base URL is not local unless the user names
  the target and says to proceed.
- These tests write (emails, tokens, failed sign-ins, sessions). That is
  expected: tell the user before the first writing request, list every write
  under "Side effects of this audit", and prefer accounts whose state the
  project's own tests already reset.
- Capture the real request first (browser dev tools, the framework's action
  or route handler, or the auth provider's public endpoint), then replay it
  with `curl` changing one thing at a time.
- Test **every public entry point to the same function**, not only the app's
  form. With a backend-as-a-service (Supabase, Firebase, Auth0) the browser
  key lets anyone call the provider's auth and data APIs directly, skipping
  the app: test `/auth/v1/recover`, `/auth/v1/verify`, `/auth/v1/user`,
  `/rest/v1/...` and the like as well as the app's pages.
- Record per test: the request (method, path, the edited header or field),
  the response (status, `Location`, body excerpt) and, for email flows, the
  link that arrived in the mail catcher.

## A. Account flows (reset, invite, email change, magic link, sign-up)

1. **Token bound to the account.** If the "set new password" request carries
   a user, email or id next to the token, change it to another account. The
   server must take the account from the token, never from the request. Same
   for invite acceptance and email-change confirmation.
2. **Reset poisoning (host header).** Request a reset for a test account while
   sending, one at a time: `X-Forwarded-Host: attacker.test`,
   `Host: attacker.test`, `X-Forwarded-Proto`, `Forwarded: host=...`,
   `X-Host`, `X-Original-Host`, `Origin`, `Referer`, and any
   `redirect_to`/`redirectTo`/`next`/`callback` parameter the endpoint
   accepts. Then open the email in the mail catcher: the link's host must be
   the configured one every time. Repeat for invite, resend and "copy link"
   features, and for links built in server code rather than in a template.
   The fix is always the same: the public origin comes from configuration.
3. **Token lifecycle.** Use a link twice (second use must fail). Request two
   links and use the first (must fail). Check the lifetime against what the
   email says. Change the password and confirm older sessions and outstanding
   reset links die. Check the token is not logged, not in a `Referer` sent to
   a third party, and not consumed by a plain GET that a mail scanner would
   fetch.
4. **Enumeration.** Compare the responses for a known and an unknown address
   on sign-in, reset, sign-up and invite: body, status, timing, and the
   rate-limit answer on the second request.
5. **Changing credentials while signed in.** Can a session alone change the
   password or the email, with no current password and no re-authentication?
6. **Sign-up paths that should be closed.** Call the provider's sign-up
   endpoint directly, with and without metadata fields that look like roles.

## B. Request trust

1. **Redirects built from the request.** For every route that redirects, send
   forged `Host` and `X-Forwarded-*` and read `Location`. Also try
   `?next=//attacker.test`, `?redirect=https:attacker.test`, backslashes and
   encoded slashes on any redirect parameter.
2. **Identifiers in the request (IDOR).** For every action that takes an id
   in the path, query, body or a hidden form field, replay it as another user
   and as another tenant: read, update, delete, and "act on behalf of". Hidden
   fields and ids inside JSON count. Include ids of rows the caller can see
   but should not be able to change.
3. **Mass assignment.** Add fields the form does not send (`role`, `is_admin`,
   owner or tenant id, timestamps, `id`) to create and update requests,
   through the app and straight at the data API. Check which columns a
   low-privilege role can actually write, not which ones the UI offers.
4. **Authorisation on the action, not the page.** Call each mutating endpoint
   or server action signed out, as a lower role and as another tenant. A
   guard on the layout or the page proves nothing about the action.
5. **Cross-site requests.** Replay state-changing requests with a foreign
   `Origin` and with none; check cookie flags (`HttpOnly`, `Secure`,
   `SameSite`) on a live signed-in response; check CORS answers for an
   arbitrary origin with credentials.
6. **Middleware and routing bypass.** Framework-internal headers
   (`x-middleware-subrequest`, `x-middleware-rewrite`, `x-nextjs-data`,
   `RSC`), path tricks (`//`, `..%2f`, case changes, trailing slash, a
   static-asset prefix in front of a protected path), and method changes
   (`HEAD`, `POST` on a GET route).
7. **Header and cache injection.** CR/LF in any value that reaches a header;
   a forged host on a cacheable page followed by a clean fetch (stored
   reflection); `Cache-Control` on responses that depend on the session or
   the host.
8. **Rate limits where the server makes the call.** If sign-in or reset goes
   through the app server, the provider sees one IP for everyone: send a
   burst and see whether one client locks out all, or nobody is limited.
9. **Uploads and fetches**, when they exist: type and size checks done on the
   server, path traversal in names, stored files served from the app's
   origin, and server-side requests to a user-supplied URL (SSRF).

## C. What to write down

A table per group: test, request sent, result, verdict (`confirmed`,
`rejected`, `needs validation`). List the entry points that were not tested
and why (needs a proxy, needs real email, not built yet). "Reviewed the reset
flow" without the requests is not evidence.

Source of group A, items 1 and 2: a public write-up of a booking platform
audit where the reset endpoint accepted another user's name with a valid
token, and after that fix built the emailed link from `X-Forwarded-Host`.
