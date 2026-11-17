"""Reviewed official v1.37.0 archives and extracted executable SHA-256 digests."""

import platform
from pathlib import Path

VERSION = "1.37.0"
# archive digest, executable digest
PINS = {
    "linux_amd64": (
        "eac87307d31d08c36800c58a409c247f1c5db37fbb72e2544402f22a87cbca3c",
        "401389ac23e81bc844093c88ae1e283fbf80ef719f400cbeb19cd36d15957971",
    ),
    "linux_arm64": (
        "072a425ac647ecf2808721e91293fd644cee7935d2b32e650b3158539b2c7898",
        "ba47242885ef53b52ef2a6e0528ae089b51d4c35171acc2d8ce73175ac558bba",
    ),
    "windows_amd64": (
        "d72f1c5c4ba4adddafa4ec3c38f1c34f09df8ddb2d2bdd75869f94145c5bcc6d",
        "b87a2a39b80cf30784d91b11f82709438a2350901a0304f0a2f9be25f72ae72d",
    ),
}


def platform_key() -> str:
    machine = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64"}.get(
        platform.machine().lower(), platform.machine().lower()
    )
    key = f"{platform.system().lower()}_{machine}"
    if key not in PINS:
        raise RuntimeError("Unsupported oasdiff platform; use the Linux backend container.")
    return key


def binary_path() -> Path:
    name = "oasdiff.exe" if platform.system() == "Windows" else "oasdiff"
    return Path(__file__).resolve().parents[1] / ".tools" / "oasdiff" / name
