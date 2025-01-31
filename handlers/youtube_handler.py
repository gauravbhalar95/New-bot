from urllib.parse import urlparse

def is_supported_domain(url):
    """
    Check if the URL belongs to a supported domain.
    """
    try:
        domain = urlparse(url).netloc
        return any(supported_domain in domain for supported_domain in SUPPORTED_DOMAINS)
    except Exception:
        return False

def get_domain(url):
    """
    Extract the domain from the URL.
    """
    return urlparse(url).netloc