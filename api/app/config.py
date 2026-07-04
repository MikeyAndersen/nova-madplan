import os

# Fase 1. Nøgler til senere faser (OLLAMA_*, BRAIN_URL, INTERNAL_API_TOKEN,
# MADPLAN_DRAIN_TOKEN, INVENTORY_POLL_MINUTES) tilføjes additivt i deres fase,
# jf. INTEGRATION_SPEC §6/§7.
DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/madplan.db")

# Bearer-token brain (og andre klienter) skal præsentere mod /api/*.
# Tomt token = auth fejler lukket (503), jf. spec §0.4 — ingen åben API.
LIFEHUB_API_TOKEN = os.getenv("LIFEHUB_API_TOKEN", "")

TIMEZONE = os.getenv("TIMEZONE", "Europe/Copenhagen")
