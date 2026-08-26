"""Test-only environment defaults; production startup still requires a real key."""
import os

os.environ.setdefault("GLM_API_KEY", "test-key-not-used-for-network-calls")
