"""Parse User-Agent strings to extract device_type, platform, and browser."""

from typing import Tuple


def detect_device(user_agent: str | None) -> Tuple[str, str, str]:
    """
    Returns (device_type, platform, browser).
    device_type: 'mobile' | 'tablet' | 'desktop'
    platform: 'iOS' | 'Android' | 'Windows' | 'macOS' | 'Linux' | 'unknown'
    browser: 'Chrome' | 'Firefox' | 'Safari' | 'Edge' | 'Opera' | 'unknown'
    """
    if not user_agent:
        return "desktop", "unknown", "unknown"

    ua = user_agent.lower()

    # --- Device type ---
    # Tablet detection before phone (iPads have "mobile" sometimes in older UA)
    is_tablet = (
        "ipad" in ua
        or ("android" in ua and "mobile" not in ua)
        or "tablet" in ua
    )
    is_mobile = (
        not is_tablet
        and (
            "mobile" in ua
            or "iphone" in ua
            or "android" in ua
            or "blackberry" in ua
            or "windows phone" in ua
        )
    )

    if is_tablet:
        device_type = "tablet"
    elif is_mobile:
        device_type = "mobile"
    else:
        device_type = "desktop"

    # --- Platform ---
    if "ipad" in ua or "iphone" in ua or "ios" in ua:
        platform = "iOS"
    elif "android" in ua:
        platform = "Android"
    elif "windows phone" in ua:
        platform = "Windows Phone"
    elif "windows" in ua:
        platform = "Windows"
    elif "macintosh" in ua or "mac os x" in ua:
        platform = "macOS"
    elif "linux" in ua:
        platform = "Linux"
    else:
        platform = "unknown"

    # --- Browser (order matters: Edge before Chrome, Chrome before Safari) ---
    if "edg/" in ua or "edge/" in ua:
        browser = "Edge"
    elif "opr/" in ua or "opera" in ua:
        browser = "Opera"
    elif "firefox/" in ua:
        browser = "Firefox"
    elif "chrome/" in ua or "crios/" in ua:
        browser = "Chrome"
    elif "safari/" in ua:
        browser = "Safari"
    else:
        browser = "unknown"

    return device_type, platform, browser
