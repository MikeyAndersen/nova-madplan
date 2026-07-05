import os

DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/madplan.db")

# Bearer-token brain (og andre klienter) skal præsentere mod /api/*.
# Tomt token = auth fejler lukket (503), jf. spec §0.4 — ingen åben API.
LIFEHUB_API_TOKEN = os.getenv("LIFEHUB_API_TOKEN", "")

TIMEZONE = os.getenv("TIMEZONE", "Europe/Copenhagen")


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


# ── Fase 4: forslags-motor (7b) + brain-lager (INTEGRATION_SPEC §4/§6) ──
# NB: brain-containeren lytter på 8300 (spec §6 skriver 8000 — rettet jf. §8).
BRAIN_URL = os.getenv("BRAIN_URL", "http://brain:8300")
INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "")   # madplan → brain inventory
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
STRONG_OLLAMA_MODEL = os.getenv("STRONG_OLLAMA_MODEL", "qwen2.5:32b-instruct")  # Fase 5
# Fase 5: 32b-drain. Tomt STRONG_OLLAMA_URL = PC'en uden for rækkevidde (online:false).
STRONG_OLLAMA_URL = os.getenv("STRONG_OLLAMA_URL", "")   # PC'ens Ollama (tunnel/LAN)
MADPLAN_DRAIN_TOKEN = os.getenv("MADPLAN_DRAIN_TOKEN", "")  # agent → madplan drain
SUGGEST_QUEUE_MAX_DAYS = _int("SUGGEST_QUEUE_MAX_DAYS", 7)  # §5 hård grænse
INVENTORY_POLL_MINUTES = _int("INVENTORY_POLL_MINUTES", 15)
SUGGEST_HARD_DAYS = _int("SUGGEST_HARD_DAYS", 14)          # §4.3 hård udelukkelse
SUGGEST_SOFT_DAYS = _int("SUGGEST_SOFT_DAYS", 7)           # §4.3 blødt loft ved <7 kandidater
FUZZY_RATIO = float(os.getenv("FUZZY_RATIO", "0.85"))     # §4.2 ingrediens-match
# Slår baggrunds-triggere fra (poll/cron/cooked). Tests sætter false.
SUGGEST_AUTO = os.getenv("SUGGEST_AUTO", "true").lower() == "true"
