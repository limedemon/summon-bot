import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Не задана переменная окружения BOT_TOKEN")

DATABASE_URL = "postgresql://bothost_db_737ab6c3c472:6miPHTwM9Ju1jX5ieznlQDP86OOvPnFdKS00oLC4C6g@node1.pghost.ru:16111/bothost_db_737ab6c3c472"

COOLDOWN_SECONDS = 5 * 60
PAGE_SIZE = 8
