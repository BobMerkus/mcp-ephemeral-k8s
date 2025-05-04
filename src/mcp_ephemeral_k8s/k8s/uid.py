"""This module contains a utility function to generate unique identifiers for MCP ephemeral K8s resources based on RFC 1123 Label Names."""

import random
import string
import time


def generate_unique_id(prefix: str | None = None, max_length: int = 63) -> str:
    """
    Generate a unique identifier that follows the Kubernetes naming rules (RFC 1123 Label Names).

    RFC 1123 Label Names must:
    - Contain only lowercase alphanumeric characters or '-'
    - Start with an alphanumeric character
    - End with an alphanumeric character
    - Be at most 63 characters

    Args:
        prefix: Optional prefix for the ID. Will be converted to lowercase and non-compliant
                characters will be replaced with dashes.
        max_length: Maximum length of the generated ID, defaults to 63 (K8s limit).

    Returns:
        A unique RFC 1123 compliant identifier string.
    """
    # Process prefix if provided
    processed_prefix = ""
    if prefix:
        # Convert to lowercase and replace invalid characters
        processed_prefix = "".join(
            c if c.isalnum() and c.islower() else (c.lower() if c.isalnum() else "-") for c in prefix
        )

        # Ensure prefix starts with alphanumeric
        if processed_prefix and not processed_prefix[0].isalnum():
            processed_prefix = f"p{processed_prefix}"

        # Add separator
        if processed_prefix:
            processed_prefix = f"{processed_prefix}-"

    # Generate a unique part (timestamp + random)
    timestamp = str(int(time.time()))
    random_chars = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))  # noqa: S311
    unique_part = f"{timestamp}-{random_chars}"

    # Combine and ensure max length
    full_id = f"{processed_prefix}{unique_part}"
    if len(full_id) > max_length:
        # If too long, truncate the ID but keep the random part
        chars_to_keep = max_length - len(random_chars) - 1
        full_id = f"{full_id[:chars_to_keep]}-{random_chars}"

    # Ensure ID ends with alphanumeric
    if not full_id[-1].isalnum():
        full_id = f"{full_id[:-1]}{random.choice(string.ascii_lowercase)}"  # noqa: S311

    return full_id


__all__ = ["generate_unique_id"]
