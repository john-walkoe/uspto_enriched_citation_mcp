"""
USPTO ODP applications search client — granted-patent-number crosswalk only.

Neither citation API can be searched by granted patent number, so a caller who
knows only a patent number needs the application serial the citation indexes DO
carry. That mapping comes from the ODP applications search endpoint, which is
the same api.uspto.gov host under the same X-API-KEY as Enriched Citations v3
and OA Citations v2.

It therefore inherits BaseCitationClient rather than opening a private httpx
client: the crosswalk call draws from the same per-instance token bucket, the
same cross-process shared limiter (`_send`), the same retry policy, and the
same response-size/content-type guards as every other outbound call. An
unmetered side channel to the same host under the same key would quietly break
the rate budget the shared limiter exists to protect.

Scope is deliberately one method: patent number in, application serial out.
"""

import time
from typing import Optional

import httpx

from .base_citation_client import BaseCitationClient
from ..config.constants import APPLICATIONS_SEARCH_PATH
from ..shared.circuit_breaker import get_circuit_breaker
from ..shared.exceptions import (
    APIConnectionError,
    APIResponseError,
    APITimeoutError,
    RateLimitError,
)
from ..util.cache import generate_cache_key
from ..util.logging import get_logger
from ..util.retry import retry_async

logger = get_logger(__name__)

# Own circuit breaker instance (bulkhead isolation, same rationale as the OA
# client): an outage on the applications endpoint must not open the circuit for
# either citation API. BaseCitationClient.__init__ resolves the same named
# instance via _CACHE_KEY_PREFIX; the module-level name is kept for tests that
# reset breaker state directly.
uspto_api_breaker = get_circuit_breaker(
    "applications_crosswalk",
    failure_threshold=3,
    recovery_timeout=30.0,
    success_threshold=2,
)


class ApplicationsCrosswalkClient(BaseCitationClient):
    """Resolve a granted patent number to its application serial.

    One POST to the ODP applications search endpoint per uncached patent
    number, asking for a single record and two fields.
    """

    _RECORDS_PATH = APPLICATIONS_SEARCH_PATH
    _CACHE_KEY_PREFIX = "applications_crosswalk"

    # The base class's two public record methods are NOT substitutable here
    # (S-1). This client inherits only for transport, as its docstring above
    # says: it sets no _FIELDS_PATH, so the inherited get_fields() would GET
    # the bare API root and count the failure against this lane's breaker;
    # and the applications endpoint takes a JSON body while the inherited
    # search_records posts form fields, so it would send a malformed request.
    # Refusing beats silently doing the wrong thing.
    async def get_fields(self):
        raise NotImplementedError(
            "ApplicationsCrosswalkClient exposes no /fields endpoint; its "
            "only operation is find_application_number()."
        )

    async def search_records(self, *args, **kwargs):
        raise NotImplementedError(
            "The applications endpoint takes a JSON body; use "
            "find_application_number()."
        )

    async def _find_application_number_raw(self, patent_number: str) -> Optional[str]:
        """One metered crosswalk call. Returns None when nothing matched.

        A patent-number miss is HTTP 404 with "No matching records found"
        (verified live 2026-09-02), which is a legitimate answer here, not a
        transport failure — it is mapped to None instead of raising, so the
        tool layer can report the miss in caller terms.
        """
        cache_key = generate_cache_key(
            f"{self._CACHE_KEY_PREFIX}_lookup", patent_number
        )
        cached = self._get_cached_search_result(cache_key)
        if cached is not None:
            return cached.get("application_number")

        start_time = time.time()
        endpoint = f"{self._CACHE_KEY_PREFIX}_search"
        if not await self.rate_limiter.acquire(endpoint=endpoint):
            raise RateLimitError("Rate limit exceeded.")

        try:
            url = f"{self.base_url}{self._RECORDS_PATH}"
            body = {
                "q": f"applicationMetaData.patentNumber:{patent_number}",
                "pagination": {"limit": 1, "offset": 0},
                "fields": [
                    "applicationNumberText",
                    "applicationMetaData.patentNumber",
                ],
            }
            response = await self._send("POST", url, json=body)

            if response.status_code == 404:
                application_number = None
            else:
                self._handle_http_error(response)
                self._validate_content_type(response)
                self._validate_response_size(response)
                application_number = self._extract_application_number(
                    response.json(), patent_number
                )

            self._set_cached_search_result(
                cache_key, {"application_number": application_number}
            )
            self.metrics_collector.record_request(
                endpoint=endpoint,
                method="POST",
                status_code=response.status_code,
                duration_seconds=time.time() - start_time,
            )
            return application_number

        except httpx.TimeoutException:
            raise APITimeoutError(
                "Patent-number crosswalk timed out", timeout_seconds=30.0
            )
        except httpx.ConnectError:
            raise APIConnectionError("Failed to connect to USPTO API")
        except httpx.HTTPError as e:
            raise APIResponseError(f"HTTP error: {str(e)}")

    @staticmethod
    def _extract_application_number(
        payload: dict, patent_number: str
    ) -> Optional[str]:
        """Pull applicationNumberText out of a patentFileWrapperDataBag hit.

        The returned patentNumber is checked against the one asked for when the
        record carries it: a hit on a different number is a match this server
        cannot justify, so it is reported as a miss rather than answering about
        the wrong application.
        """
        bag = payload.get("patentFileWrapperDataBag") or []
        if not bag:
            return None
        record = bag[0] or {}
        returned = (record.get("applicationMetaData") or {}).get("patentNumber")
        if returned and str(returned).strip() != patent_number:
            logger.info("Crosswalk hit did not match the requested patent number")
            return None
        application_number = record.get("applicationNumberText")
        return str(application_number).strip() if application_number else None

    @retry_async(max_attempts=3, base_delay=1.0, max_delay=30.0)
    async def _find_application_number_impl(
        self, patent_number: str
    ) -> Optional[str]:
        return await self._circuit_breaker.call(
            self._find_application_number_raw, patent_number
        )

    async def find_application_number(self, patent_number: str) -> Optional[str]:
        """Public entry point: application serial for `patent_number`, or None."""
        return await self._find_application_number_impl(patent_number)
