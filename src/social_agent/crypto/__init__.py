"""Secret sealing helpers."""

from social_agent.crypto.fernet_box import FernetBoxError, generate_key, seal, unseal

__all__ = ["FernetBoxError", "generate_key", "seal", "unseal"]
