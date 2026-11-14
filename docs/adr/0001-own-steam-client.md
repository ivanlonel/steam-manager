# Own Steam client instead of a third-party Steam library

Every call the application needs for its store and account data is a plain HTTPS JSON request,
and the candidate libraries were a poor fit: `pysteam-client` (the H47R15 fork of
ValvePython/steam) is gevent-based, typed only in part, declared for Python 3.13 and maintained
by one person; ValvePython/steam last released in 2022; steamio is bot-oriented;
python-steam-api covers documented methods only. We therefore write our own typed client
(httpx plus a Pydantic model per answer), and when client-protocol data arrives (licenses, PICS,
cloud config) we implement that protocol ourselves over WebSocket with `protobuf` modules
generated from SteamDatabase/Protobufs, rather than take a Steam library into the core.

## Consequences

- Undocumented endpoints break without notice and no upstream will fix them for us; the quirks
  found so far are recorded as tests.
- The protocol client is the riskiest part of the project and cannot be tested against Steam in
  CI, so each capability needs a live check before it ships.
