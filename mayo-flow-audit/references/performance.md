# Performance dimension (audit dimension 2)

Moved out of `SKILL.md`; read in full before auditing performance.

2. **Performance.** Start from what the user *waits on*, not from the
   slowest query. Walk each user journey (cold launch, the main action, the
   last step of a flow, every tab and screen entry) and list, per step, the
   sequence of loading states the user actually sees. Look for:
   - **Double loading:** a spinner or skeleton that closes and is followed by
     another one for data that was already known or fetched (a response that
     carries a row and the client re-reads it; a wait dialog that closes
     before the next screen's data is in hand). One wait should cover one
     journey step.
   - **Fetch-on-arrival:** data requested only after navigating to the
     screen that needs it, when the previous screen could have started it
     (prefetch while the user is reading, rating or typing).
   - **Waterfalls:** sequential awaits or dependent providers on the same
     path that do not depend on each other (parallelise); work gated on a
     slow signal it does not need (a connection handshake, a status event).
   - **Cold-start cost:** a connection, socket, cache or SDK that is opened
     lazily at the moment the user is waiting; token, session and config
     lookups repeated per request.
   - **Server side:** round trips per request, N+1 reads, unindexed filters
     and foreign keys, unbounded growth (logs, caches), work repeated per
     call that could be cached, payloads larger than the screen uses.
   - **Client side:** rebuilds and animations that keep running off-screen,
     per-tick `setState`, lists built eagerly, repeated invalidation on
     navigation.
   Rank findings by the wait a person feels times how often they hit it, not
   by how bad the code looks. Prefer measured numbers (device timings, query
   plans, logs); mark the rest "reasoned, not measured". A MEDIUM-or-higher
   performance finding still open at the next round is escalated in the
   summary (owner decides: fix, defer with a date, or accept), never
   silently carried as "STILL OPEN".
