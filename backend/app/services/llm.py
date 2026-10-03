import os
import base64
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq


class LLMConfigurationError(RuntimeError):
    """Raised when hosted inference has not been configured for the backend."""


class LLMServiceError(RuntimeError):
    """Raised when the configured hosted model does not return usable text."""


MINIMUM_COMPLETION_TOKENS = 1024


def _assistant_text(response: object) -> str | None:
    """Read the normal non-streaming Groq SDK assistant content field."""
    choices = getattr(response, "choices", None)
    if not choices:
        return None

    content = getattr(choices[0].message, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()
    return None


def complete(system_prompt: str, user_prompt: str, max_tokens: int) -> str:
    """Generate text through Groq without exposing credentials beyond the backend."""
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    api_key = os.getenv("GROQ_API_KEY")
    model = os.getenv("GROQ_MODEL")
    if not api_key or not model:
        raise LLMConfigurationError(
            "Hosted LLM is not configured. Set GROQ_API_KEY and GROQ_MODEL in the backend environment."
        )

    try:
        response = Groq(api_key=api_key).chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            # GPT-OSS uses reasoning tokens before producing message.content.
            # A 220-token cap can end generation before the final assistant text.
            max_completion_tokens=max(max_tokens, MINIMUM_COMPLETION_TOKENS),
            include_reasoning=False,
        )
    except Exception as error:
        raise LLMServiceError("The hosted LLM request failed.") from error

    content = _assistant_text(response)
    if content is None:
        raise LLMServiceError("The hosted LLM returned no usable text.")
    return content


def complete_vision(image_path: Path, mime_type: str, prompt: str) -> str:
    """Analyze one locally stored image through the separately configured vision model."""
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    api_key = os.getenv("GROQ_API_KEY")
    model = os.getenv("GROQ_VISION_MODEL")
    if not api_key or not model:
        raise LLMConfigurationError(
            "Hosted vision is not configured. Set GROQ_API_KEY and GROQ_VISION_MODEL in the backend environment."
        )

    encoded_image = base64.b64encode(image_path.read_bytes()).decode("ascii")
    try:
        response = Groq(api_key=api_key).chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{encoded_image}"},
                        },
                    ],
                }
            ],
            temperature=0.2,
            max_completion_tokens=1024,
            response_format={"type": "json_object"},
        )
    except Exception as error:
        raise LLMServiceError("The hosted vision request failed.") from error

    content = _assistant_text(response)
    if content is None:
        raise LLMServiceError("The hosted vision model returned no usable text.")
    return content
