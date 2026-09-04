import ipaddress

import httpx

from app import config


def is_public_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return not (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved)


class Provider:
    """One upstream. `needs_public_ip` is what keeps the mocks usable from
    localhost, where a real lookup service has nothing to say."""

    name = "provider"
    needs_public_ip = True

    def lookup(self, ip: str, client: httpx.Client) -> dict:
        raise NotImplementedError


class IpApiProvider(Provider):
    """ip-api.com — free, no key, 45 requests a minute."""

    name = "ip-api.com"

    def lookup(self, ip: str, client: httpx.Client) -> dict:
        response = client.get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "status,message,country,countryCode,city"},
        )
        response.raise_for_status()
        body = response.json()
        if body.get("status") != "success":
            raise ValueError(body.get("message", "lookup failed"))
        return {"country": body.get("country"), "country_code": body.get("countryCode"), "city": body.get("city")}


class IpApiCoProvider(Provider):
    """ipapi.co — the second opinion, ~1,000 lookups a day free."""

    name = "ipapi.co"

    def lookup(self, ip: str, client: httpx.Client) -> dict:
        response = client.get(f"https://ipapi.co/{ip}/json/")
        response.raise_for_status()
        body = response.json()
        if body.get("error"):
            raise ValueError(body.get("reason", "lookup failed"))
        return {"country": body.get("country_name"), "country_code": body.get("country_code"), "city": body.get("city")}


class MockProvider(Provider):
    """Answers the same thing every time, from any IP.

    The brief asks for the fallback proof to be deterministic, and a real
    service that happens to be up is not a proof of anything.
    """

    needs_public_ip = False

    def __init__(self, name: str, answer: dict):
        self.name = name
        self.answer = answer

    def lookup(self, ip: str, client: httpx.Client) -> dict:
        return dict(self.answer)


PROVIDERS = {
    "ipapi": IpApiProvider(),
    "ipapico": IpApiCoProvider(),
    "mock_a": MockProvider("mock_a", {"country": "Spain", "country_code": "ES", "city": "Madrid"}),
    "mock_b": MockProvider("mock_b", {"country": "Germany", "country_code": "DE", "city": "Berlin"}),
}

EMPTY = {"country": None, "country_code": None, "city": None, "geo_provider": None}


class GeoService:
    """Turns an IP into a country and city, or gives up quietly.

    Nothing in here is allowed to raise. Losing the geo data costs a column;
    losing the submission costs a customer a lead.
    """

    def __init__(self, provider_names: list[str], timeout: float, down: set[str], forced_ip: str = ""):
        self.providers = [PROVIDERS[name] for name in provider_names if name in PROVIDERS]
        self.timeout = timeout
        self.down = down
        self.forced_ip = forced_ip

    @classmethod
    def from_config(cls):
        # The A/B switches point at positions in the chain, not at names, so the
        # same toggle works whichever providers are configured.
        down = set()
        if config.GEO_PROVIDER_A_DOWN:
            down.add(0)
        if config.GEO_PROVIDER_B_DOWN:
            down.add(1)
        return cls(config.GEO_PROVIDERS, config.GEO_TIMEOUT_SECONDS, down, config.GEO_FORCE_CLIENT_IP)

    def enrich(self, ip: str) -> dict:
        lookup_ip = self.forced_ip or ip
        if not lookup_ip:
            return {**EMPTY, "geo_status": "skipped_no_ip"}

        public = is_public_ip(lookup_ip)
        attempted = False

        with httpx.Client(timeout=self.timeout, headers={"User-Agent": "flyrank-widget-platform"}) as client:
            for position, provider in enumerate(self.providers):
                if position in self.down:
                    print(f"geo: {provider.name} marked down, skipping")
                    continue
                if provider.needs_public_ip and not public:
                    continue
                attempted = True
                try:
                    result = provider.lookup(lookup_ip, client)
                except Exception as error:
                    # Any failure is the same failure: try the next one.
                    print(f"geo: {provider.name} failed ({type(error).__name__}), falling back")
                    continue
                if result.get("country") or result.get("city"):
                    return {**result, "geo_provider": provider.name, "geo_status": "ok"}

        if not attempted and not public:
            return {**EMPTY, "geo_status": "skipped_private_ip"}
        print("geo: no provider answered, storing without location")
        return {**EMPTY, "geo_status": "unavailable"}
