import hashlib
import io
import tarfile

import pytest

import install_oasdiff


@pytest.mark.parametrize("fault", [None, "archive", "binary", "symlink"])
def test_install_verifies_both_hashes_and_extracts_only_fixed_member(monkeypatch, tmp_path, fault):
    content = b"synthetic binary, never executed"
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as tar:
        member = tarfile.TarInfo("oasdiff")
        member.size = len(content)
        if fault == "symlink":
            member.type = tarfile.SYMTYPE
            member.linkname = "../outside"
        tar.addfile(member, io.BytesIO(content))
        license_member = tarfile.TarInfo("LICENSE")
        license_member.size = 7
        tar.addfile(license_member, io.BytesIO(b"license"))
        extra = tarfile.TarInfo("../outside")
        tar.addfile(extra, io.BytesIO())
    data = archive.getvalue()
    pins = (hashlib.sha256(data).hexdigest(), hashlib.sha256(content).hexdigest())
    if fault == "archive":
        pins = ("0" * 64, pins[1])
    if fault == "binary":
        pins = (pins[0], "0" * 64)
    destination = tmp_path / "tools" / "oasdiff"
    monkeypatch.setattr(install_oasdiff, "platform_key", lambda: "linux_amd64")
    monkeypatch.setattr(install_oasdiff, "PINS", {"linux_amd64": pins})
    monkeypatch.setattr(install_oasdiff, "binary_path", lambda: destination)
    monkeypatch.setattr(install_oasdiff.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(data))
    if fault:
        with pytest.raises(RuntimeError):
            install_oasdiff.install()
        assert not destination.exists()
    else:
        install_oasdiff.install()
        assert destination.read_bytes() == content
        assert (destination.parent / "LICENSE").read_bytes() == b"license"
    assert not (tmp_path / "outside").exists()
