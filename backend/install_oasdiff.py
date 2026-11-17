"""Install the pinned CLI; never downloads or executes uploaded document content."""

import hashlib
import io
import tarfile
import urllib.request

from app.oasdiff_pin import PINS, VERSION, binary_path, platform_key


def install() -> None:
    key = platform_key()
    archive_hash, executable_hash = PINS[key]
    url = (
        f"https://github.com/oasdiff/oasdiff/releases/download/v{VERSION}/"
        f"oasdiff_{VERSION}_{key}.tar.gz"
    )
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read(60 * 1024 * 1024 + 1)
    if len(data) > 60 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != archive_hash:
        raise RuntimeError("oasdiff archive checksum mismatch or size limit exceeded")
    destination = binary_path()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        member = archive.getmember(destination.name)
        if not member.isfile() or member.size > 60 * 1024 * 1024:
            raise RuntimeError("Invalid oasdiff archive member")
        stream = archive.extractfile(member)
        if stream is None:
            raise RuntimeError("Missing oasdiff executable")
        executable = stream.read()
        license_member = archive.getmember("LICENSE")
        if not license_member.isfile() or license_member.size > 100_000:
            raise RuntimeError("Invalid oasdiff license member")
        license_stream = archive.extractfile(license_member)
        if license_stream is None:
            raise RuntimeError("Missing oasdiff license")
        license_text = license_stream.read()
    if hashlib.sha256(executable).hexdigest() != executable_hash:
        raise RuntimeError("oasdiff executable checksum mismatch")
    destination.parent.mkdir(parents=True, exist_ok=True)
    (destination.parent / "LICENSE").write_bytes(license_text)
    temporary = destination.with_suffix(".download")
    temporary.write_bytes(executable)
    temporary.chmod(0o755)
    temporary.replace(destination)
    print(f"Installed verified oasdiff {VERSION} for {key}")


if __name__ == "__main__":
    install()
