"""MAX-scoped TLS trust; never changes certifi or the system certificate store."""
import os
import ssl
from pathlib import Path
import certifi


def max_ca_file():
    path = Path(os.getenv('MAX_CA_BUNDLE') or Path(__file__).resolve().parents[1] / 'certs/russian_trusted_root_ca_pem.crt')
    if not path.is_file():
        raise ValueError('Не найден доверенный сертификат MAX')
    return str(path)


def max_ssl_context():
    context = ssl.create_default_context(cafile=certifi.where())
    context.load_verify_locations(cafile=max_ca_file())
    return context
