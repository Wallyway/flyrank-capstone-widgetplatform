import hashlib
import secrets

WIDGET_ID_PREFIX = "wgt_"
API_KEY_PREFIX = "wpk_"


# Random and not sequential: this id ends up in a public URL, so an integer
# would let anyone list every widget by counting up.
def new_widget_id() -> str:
    return WIDGET_ID_PREFIX + secrets.token_hex(8)


def new_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


# Only the hash is stored. No salt because the key is already 32 random bytes,
# and an unsalted digest keeps the lookup a single indexed query.
def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
