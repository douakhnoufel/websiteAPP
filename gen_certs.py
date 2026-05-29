import datetime
import ipaddress
import socket
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


BASE_DIR = Path(__file__).resolve().parent
KEY_PATH = BASE_DIR / "key.pem"
CERT_PATH = BASE_DIR / "cert.pem"


def local_ipv4_addresses() -> set[str]:
    addresses = {"127.0.0.1"}

    for raw in sys.argv[1:]:
        try:
            addresses.add(str(ipaddress.IPv4Address(raw)))
        except ValueError:
            pass

    try:
        hostname = socket.gethostname()
        for raw in socket.gethostbyname_ex(hostname)[2]:
            try:
                addresses.add(str(ipaddress.IPv4Address(raw)))
            except ValueError:
                pass
    except OSError:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            addresses.add(sock.getsockname()[0])
    except OSError:
        pass

    return addresses


def cert_has_addresses(addresses: set[str]) -> bool:
    if not KEY_PATH.exists() or not CERT_PATH.exists():
        return False

    try:
        cert = x509.load_pem_x509_certificate(CERT_PATH.read_bytes())
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        cert_ips = {str(ip) for ip in san.get_values_for_type(x509.IPAddress)}
        cert_names = set(san.get_values_for_type(x509.DNSName))
    except Exception:
        return False

    required_names = {"localhost"}
    return addresses.issubset(cert_ips) and required_names.issubset(cert_names)


def build_certificate(addresses: set[str]) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    common_name = next((ip for ip in sorted(addresses) if not ip.startswith("127.")), "localhost")
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    alt_names = [x509.DNSName("localhost")]

    for raw in sorted(addresses):
        alt_names.append(x509.IPAddress(ipaddress.IPv4Address(raw)))

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .sign(key, hashes.SHA256())
    )

    KEY_PATH.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    CERT_PATH.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def main() -> None:
    addresses = local_ipv4_addresses()
    if cert_has_addresses(addresses):
        print("HTTPS certificate already covers: " + ", ".join(sorted(addresses)))
        return

    build_certificate(addresses)
    print("HTTPS certificate generated for: " + ", ".join(sorted(addresses)))


if __name__ == "__main__":
    main()
