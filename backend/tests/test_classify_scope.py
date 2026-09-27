import pytest

from app.recon.classify import ClassifyError, InputType, classify
from app.recon.scope import in_scope


@pytest.mark.parametrize(
    "raw,kind,value",
    [
        ("example.com", InputType.DOMAIN, "example.com"),
        ("  Sub.Example.COM. ", InputType.DOMAIN, "sub.example.com"),
        ("bücher.de", InputType.DOMAIN, "xn--bcher-kva.de"),
        ("8.8.8.8", InputType.IP, "8.8.8.8"),
        ("[2001:db8::1]", InputType.IP, "2001:db8::1"),
        ("10.0.0.5/8", InputType.CIDR, "10.0.0.0/8"),
        ("AS15169", InputType.ASN, "AS15169"),
        ("as 13335", InputType.ASN, "AS13335"),
        ("https://example.com/a?b=1", InputType.URL, "https://example.com/a?b=1"),
        ("44d88612fea8a8f36de82e1278abb02f", InputType.HASH, "44d88612fea8a8f36de82e1278abb02f"),
        ("A" * 64, InputType.HASH, "a" * 64),
    ],
)
def test_classify(raw, kind, value):
    t = classify(raw)
    assert t.type == kind
    assert t.value == value


def test_url_host():
    t = classify("http://1.2.3.4:8080/x")
    assert t.host == "1.2.3.4"
    assert t.host_type == InputType.IP


@pytest.mark.parametrize("raw", ["", "someone@example.com", "not a domain", "10.0.0.0/99", "http://"])
def test_classify_rejects(raw):
    with pytest.raises(ClassifyError):
        classify(raw)


def test_email_rejected_with_scope_message():
    with pytest.raises(ClassifyError, match="out of scope"):
        classify("a@b.com")


@pytest.mark.parametrize(
    "raw,entries,expected",
    [
        ("example.com", [], True),
        ("example.com", ["example.com"], True),
        ("api.example.com", ["example.com"], True),
        ("badexample.com", ["example.com"], False),
        ("api.example.com", ["*.example.com"], True),
        ("10.1.2.3", ["10.0.0.0/8"], True),
        ("11.1.2.3", ["10.0.0.0/8"], False),
        ("10.1.0.0/16", ["10.0.0.0/8"], True),
        ("10.0.0.0/7", ["10.0.0.0/8"], False),
        ("https://shop.example.com/x", ["example.com"], True),
        ("AS64500", ["as64500"], True),
        ("AS64501", ["as64500"], False),
        ("44d88612fea8a8f36de82e1278abb02f", ["example.com"], True),
    ],
)
def test_scope(raw, entries, expected):
    assert in_scope(classify(raw), entries) is expected
