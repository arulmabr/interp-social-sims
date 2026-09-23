"""Select a saved credential for this process without changing the HF login."""
from huggingface_hub.utils._auth import get_stored_tokens


def resolve_token(name=None):
    if name is None:
        return None  # Hugging Face's normal environment/cached-token resolution.
    token = get_stored_tokens().get(name)
    if not token:
        raise ValueError("Requested saved Hugging Face token was not found")
    return token
