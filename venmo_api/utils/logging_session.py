import orjson
from devtools import pformat
from loguru import logger
from requests import PreparedRequest, Response, Session

MAX_BODY_LOG = 1024 * 100  # 100 KB limit to avoid OOM in logs; tweak as needed


def safe_text(b: bytes | None, fallback_repr=True):
    if b is None:
        return "<none>"
    try:
        text = b.decode("utf-8")
        if len(text) <= MAX_BODY_LOG:
            return orjson.loads(text)
        else:
            return text[:MAX_BODY_LOG] + "\n...TRUNCATED..."
    except Exception:
        if fallback_repr:
            return repr(b[:MAX_BODY_LOG]) + (
                "...TRUNCATED..." if len(b) > MAX_BODY_LOG else ""
            )
        return "<binary>"


class LoggingSession(Session):
    def send(self, request: PreparedRequest, **kwargs) -> Response:
        logger.info(f"→ {request.method} {request.url}")
        logger.debug(f"→ Request headers: {pformat(dict(request.headers))}")
        # request.body may be bytes, str, file-like, or generator. Try to show it safely.
        body = request.body
        # if hasattr(body, "read"):
        #     try:
        #         pos = body.tell()
        #         body.seek(0)
        #         content = body.read()
        #         body.seek(pos)
        #         logger.debug(f"→ Request body (file-like): {safe_text(content)}")
        #     except Exception:
        #         logger.debug("→ Request body: (file-like, unreadable)")
        # else:
        if isinstance(body, str):
            logger.debug(f"→ Request body (str): {pformat(safe_text(body.encode()))}")
        elif isinstance(body, bytes):
            logger.debug(f"→ Request body (bytes): {pformat(safe_text(body))}")
        elif body is None:
            logger.debug("→ Request body: <none>")
        else:
            # could be generator/iterable (multipart streaming)
            logger.debug(f"→ Request body: (type={type(body).__name__}) {repr(body)}")

        resp = super().send(request, **kwargs)

        logger.info(f"← {resp.status_code} {resp.reason}")
        logger.debug(f"← Response headers: {pformat(dict(resp.headers))}")

        # careful: .content will load the whole response into memory
        try:
            content = resp.content
            logger.debug(f"← Response body: {pformat(safe_text(content))}")
        except Exception as e:
            logger.debug(f"← Response body: <unreadable: {e}>")

        return resp
