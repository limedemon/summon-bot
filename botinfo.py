"""Runtime info about the bot itself, fetched once on startup.

`BOT_USERNAME` is filled in main.py right after the Bot object is created, so
handlers can build deep links (https://t.me/<username>?start=...) without doing
an extra getMe call on every update.
"""

BOT_USERNAME: str | None = None
