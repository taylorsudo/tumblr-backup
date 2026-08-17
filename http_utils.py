import time
import requests

MAX_RETRIES = 5
RATE_LIMIT_BASE_DELAY = 1.0


def requests_with_retry(method: str, url: str, max_retries: int = MAX_RETRIES, **kwargs):
    delay = RATE_LIMIT_BASE_DELAY

    for attempt in range(1, max_retries + 1):
        try:
            r = requests.request(method, url, **kwargs)

            if r.status_code == 429:
                try:
                    wait = int(r.headers.get("Retry-After", delay))
                except ValueError:
                    wait = delay  # Fallback to your base delay
                time.sleep(wait)
                delay *= 2
                continue

            r.raise_for_status()
            return r

        except requests.RequestException:
            if attempt == max_retries:
                return None
            time.sleep(delay * (2 ** (attempt - 1)))

    return None
