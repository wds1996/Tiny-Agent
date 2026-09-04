import os

from tiny_agent.integrations.settings import ServiceSettings


os.environ.setdefault("TINY_AGENT_ENVIRONMENT", "dev")
os.environ.setdefault("TINY_AGENT_MAX_CONCURRENCY", "6")
os.environ.setdefault("TINY_AGENT_MODEL_API_KEY", "demo-do-not-use-real-secrets-here")

settings = ServiceSettings(_env_file=None)
print(settings.safe_summary())
print("Secret configured?", settings.model_api_key is not None)
print("Do not print get_secret_value() in application logs.")
