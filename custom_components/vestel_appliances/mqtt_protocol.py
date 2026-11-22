"""AWS IoT WebSocket signing and exact device-owned topic selection."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import hmac
from urllib.parse import quote

ENDPOINT = "aa8u5ipzaqyfu-ats.iot.eu-west-1.amazonaws.com"
REGION = "eu-west-1"


def websocket_path(credentials, now=None):
    """AWS IoT requires adding the session token *after* calculating SigV4.

    https://docs.aws.amazon.com/iot/latest/developerguide/iam-users-groups-roles.html
    """
    now = now or datetime.now(timezone.utc)
    date = now.strftime("%Y%m%d")
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    scope = f"{date}/{REGION}/iotdevicegateway/aws4_request"
    params = {"X-Amz-Algorithm": "AWS4-HMAC-SHA256",
              "X-Amz-Credential": credentials["access_key"] + "/" + scope,
              "X-Amz-Date": stamp, "X-Amz-Expires": "900", "X-Amz-SignedHeaders": "host"}
    query = "&".join(quote(k, safe="-_.~") + "=" + quote(v, safe="-_.~") for k, v in sorted(params.items()))
    canonical = "GET\n/mqtt\n" + query + f"\nhost:{ENDPOINT}\n\nhost\n" + hashlib.sha256(b"").hexdigest()
    to_sign = "AWS4-HMAC-SHA256\n" + stamp + "\n" + scope + "\n" + hashlib.sha256(canonical.encode()).hexdigest()
    key = ("AWS4" + credentials["secret_key"]).encode()
    for item in (date, REGION, "iotdevicegateway", "aws4_request"):
        key = hmac.new(key, item.encode(), hashlib.sha256).digest()
    signature = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
    return "/mqtt?" + query + "&X-Amz-Signature=" + signature + "&X-Amz-Security-Token=" + quote(credentials["session_token"], safe="-_.~")


def subscription_topics(devices):
    """APK AwsIotServiceImpl: exact shadow/update/accepted topic per device.

    No wildcard subscription, command topic, or account-wide topic is used.
    """
    topics = {}
    for uuid, device in devices.items():
        if not isinstance(uuid, str) or not uuid or len(uuid) > 128 or any(c in uuid for c in ("#", "+", "/", "\0")):
            continue
        topic = f"$aws/things/{uuid}/shadow/update/accepted"
        topics.setdefault(topic, set()).add(uuid)
    return topics
