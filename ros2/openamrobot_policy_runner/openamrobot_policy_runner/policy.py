"""
Policy placeholder for the runner skeleton.

The runner never downloads model weights. A future policy implementation loads weights only
from a local path whose sha256 matches a dataset registry release; no such loader exists yet.
"""


class PolicyUnavailableError(RuntimeError):
    """Raised when inference is requested and no policy is loaded."""


class NoPolicy:
    """Default policy: no model is loaded, so every inference request fails."""

    def infer(self, observation):
        """Raise, because no policy is loaded; the runner treats this as an inference error."""
        raise PolicyUnavailableError('no policy loaded')
