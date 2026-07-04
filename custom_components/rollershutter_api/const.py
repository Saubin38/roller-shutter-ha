"""Constantes pour l'intégration Roller Shutter API."""

DOMAIN = "rollershutter_api"

# Config
CONF_API_KEY = "api_key"
CONF_SSL = "ssl"
CONF_API_PATH = "api_path"

DEFAULT_PORT = 8080
DEFAULT_SSL = False
DEFAULT_SCAN_INTERVAL = 30  # secondes
DEFAULT_API_PATH = "/api/rhollershutter"

# Header utilisé pour l'authentification par clé API.
# A adapter ici si ton backend Spring attend un autre header
# (ex: "Authorization" avec valeur "Bearer <clé>").
API_KEY_HEADER = "API-KEY"

# Timeout des requêtes HTTP vers l'API (secondes)
REQUEST_TIMEOUT = 10
