# Quarantined legacy scripts

This directory is excluded from default pytest discovery. Its historical API script is deliberately fail-closed: it must not contact a running application or perform registration/login requests.

Use the canonical isolated Docker/Testcontainers API gate command documented in the repository README.md. These archived scripts are not validated tests.
