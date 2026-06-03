import time
import functools
import traceback
from typing import Callable, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import openai


def with_retry(max_attempts: int = 3, delay: float = 2.0):
    """Decorator for retrying functions on transient failures."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_error = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except (openai.RateLimitError, openai.APITimeoutError) as e:
                    last_error = e
                    wait_time = delay * (2 ** (attempt - 1))
                    print(f"[Retry] Attempt {attempt}/{max_attempts} failed: {e}. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                except openai.AuthenticationError as e:
                    raise RuntimeError(f"OpenAI authentication failed. Check your API key: {e}") from e
                except Exception as e:
                    last_error = e
                    if attempt < max_attempts:
                        print(f"[Retry] Attempt {attempt}/{max_attempts} failed: {e}. Retrying...")
                        time.sleep(delay)
                    else:
                        break
            raise RuntimeError(f"All {max_attempts} attempts failed. Last error: {last_error}")
        return wrapper
    return decorator


def handle_llm_error(func: Callable) -> Callable:
    """Wraps a function with standardized LLM error handling."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except openai.RateLimitError:
            return {"error": "rate_limit", "message": "OpenAI rate limit reached. Please wait and retry."}
        except openai.AuthenticationError:
            return {"error": "auth_error", "message": "Invalid OpenAI API key."}
        except openai.APIConnectionError:
            return {"error": "connection_error", "message": "Cannot connect to OpenAI API. Check network."}
        except openai.BadRequestError as e:
            return {"error": "bad_request", "message": f"Invalid request: {e}"}
        except Exception as e:
            return {"error": "unknown", "message": str(e), "traceback": traceback.format_exc()}
    return wrapper


def safe_json_parse(text: str, fallback: Optional[dict] = None) -> dict:
    """Safely parse JSON with a fallback value."""
    import json
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
    return fallback or {}
