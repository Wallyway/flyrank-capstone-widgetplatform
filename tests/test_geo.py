import httpx
import pytest

from app.services.geo import GeoService, MockProvider, Provider, is_public_ip

PUBLIC_IP = "8.8.8.8"


class DeadProvider(Provider):
    """An upstream that is up enough to answer, and answers with an error."""

    name = "dead"
    needs_public_ip = False

    def lookup(self, ip, client):
        raise httpx.ConnectError("connection refused")


def chain(*providers):
    service = GeoService([], timeout=0.5, down=set())
    service.providers = list(providers)
    return service


A = MockProvider("mock_a", {"country": "Spain", "country_code": "ES", "city": "Madrid"})
B = MockProvider("mock_b", {"country": "Germany", "country_code": "DE", "city": "Berlin"})


def test_the_first_provider_answers():
    result = chain(A, B).enrich(PUBLIC_IP)
    assert result["geo_status"] == "ok"
    assert result["geo_provider"] == "mock_a"
    assert result["city"] == "Madrid"


def test_provider_a_down_means_b_answers():
    service = chain(A, B)
    service.down = {0}
    result = service.enrich(PUBLIC_IP)
    assert result["geo_status"] == "ok"
    assert result["geo_provider"] == "mock_b"
    assert result["city"] == "Berlin"


def test_a_provider_that_raises_falls_through_to_the_next():
    result = chain(DeadProvider(), B).enrich(PUBLIC_IP)
    assert result["geo_status"] == "ok"
    assert result["geo_provider"] == "mock_b"


def test_all_providers_down_degrades_instead_of_failing():
    service = chain(A, B)
    service.down = {0, 1}
    result = service.enrich(PUBLIC_IP)
    assert result["geo_status"] == "unavailable"
    assert result["country"] is None
    assert result["geo_provider"] is None


def test_every_provider_raising_still_returns_a_dict():
    result = chain(DeadProvider(), DeadProvider()).enrich(PUBLIC_IP)
    assert result["geo_status"] == "unavailable"


def test_a_private_address_is_never_sent_to_a_lookup_service():
    class Tripwire(Provider):
        name = "tripwire"

        def lookup(self, ip, client):
            raise AssertionError("a private address must not reach a provider")

    result = chain(Tripwire()).enrich("127.0.0.1")
    assert result["geo_status"] == "skipped_private_ip"


def test_no_ip_at_all_is_recorded_as_such():
    assert chain(A).enrich("")["geo_status"] == "skipped_no_ip"


@pytest.mark.parametrize(
    "value,expected",
    [("8.8.8.8", True), ("127.0.0.1", False), ("192.168.1.4", False), ("10.0.0.1", False), ("nonsense", False)],
)
def test_public_address_detection(value, expected):
    assert is_public_ip(value) is expected
