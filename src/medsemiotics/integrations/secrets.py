"""Reading secrets from the store a deployment actually mounts.

A secret manager reaches a running process in one of two shapes: an environment variable, or a file
in a mounted directory. This module reads both and nothing else — no secret-manager SDK is a
dependency, because both shapes are the platform's own delivery mechanism.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from medsemiotics.domain.exceptions import SecretStoreError

SECRET_DIRECTORY_ENV_VAR = "MEDSEMIOTICS_CLASSROOM_SECRET_DIR"


class SecretSource(Protocol):
    """Read one named secret from a store that lives outside the repository."""

    def read(self, name: str) -> str | None:
        """Return the secret's value, or None when this source does not hold it."""
        ...


class EnvironmentSecretSource:
    """Read secrets from environment variables.

    Cloud Run and Kubernetes both expose a secret manager version as an environment variable, so
    this covers the managed case as well as local operator shells.
    """

    def __init__(self, env: Mapping[str, str]) -> None:
        """Initialize with the environment mapping to read."""
        self._env = env

    def read(self, name: str) -> str | None:
        """Return the variable's value, treating blank as absent."""
        value = (self._env.get(name) or "").strip()
        return value or None


class FileSecretSource:
    """Read secrets from a mounted directory, one file per secret.

    This is the shape a secret manager takes when its versions are mounted as a volume: the file
    name is the secret name and the file body is the value. Nothing is cached, so a rotated secret
    is picked up on the next read.
    """

    def __init__(self, directory: Path) -> None:
        """Initialize with the directory the secret store mounts."""
        self._directory = directory

    def read(self, name: str) -> str | None:
        """Return the file's contents, treating a missing or blank file as absent.

        Raises:
            SecretStoreError: If the file exists but cannot be read or decoded.
        """
        path = self._directory / name
        if not path.is_file():
            return None
        try:
            value = path.read_text(encoding="utf-8").strip()
        except (OSError, ValueError) as err:
            msg = (
                f"Failed to read the mounted secret '{name}' "
                f"({type(err).__name__}); its location and value are withheld."
            )
            raise SecretStoreError(msg) from None
        return value or None


class ChainedSecretSource:
    """Read from several sources in order, taking the first that holds the secret."""

    def __init__(self, *sources: SecretSource) -> None:
        """Initialize with the sources to consult in precedence order."""
        self._sources = sources

    def read(self, name: str) -> str | None:
        """Return the first non-empty value any source holds."""
        for source in self._sources:
            value = source.read(name)
            if value:
                return value
        return None


def build_secret_source(env: Mapping[str, str]) -> SecretSource:
    """Build the secret source described by the environment.

    A mounted secret directory takes precedence over environment variables, so a deployment can
    rotate a secret in its store without redeploying to change a variable.

    Args:
        env: Environment mapping, which may point at a mounted secret directory.

    Returns:
        The secret source to read credentials from.
    """
    directory = (env.get(SECRET_DIRECTORY_ENV_VAR) or "").strip()
    environment_source = EnvironmentSecretSource(env)
    if not directory:
        return environment_source
    return ChainedSecretSource(FileSecretSource(Path(directory)), environment_source)
