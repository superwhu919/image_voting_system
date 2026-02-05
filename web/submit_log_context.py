# Context for submit_timing logs (set per request in api_submit)
import contextvars

submit_request_id = contextvars.ContextVar("submit_request_id", default="-")
submit_client_ip = contextvars.ContextVar("submit_client_ip", default="-")
submit_user_id = contextvars.ContextVar("submit_user_id", default="-")


def set_submit_log_context(*, request_id: str, client_ip: str, user_id: str):
    """Set context for the current request so submit_timing logs include them."""
    submit_request_id.set(request_id)
    submit_client_ip.set(client_ip)
    submit_user_id.set(user_id)
