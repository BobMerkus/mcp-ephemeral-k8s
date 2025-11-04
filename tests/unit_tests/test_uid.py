"""Unit tests for UID generation."""

import re

from mcp_ephemeral_k8s.k8s.uid import generate_unique_id


def test_generate_unique_id_no_prefix():
    """Test generating unique ID without prefix."""
    uid = generate_unique_id()

    # Check RFC 1123 compliance
    assert len(uid) <= 63
    assert uid[0].isalnum()
    assert uid[-1].isalnum()
    assert re.match(r"^[a-z0-9][-a-z0-9]*[a-z0-9]$", uid)


def test_generate_unique_id_with_prefix():
    """Test generating unique ID with prefix."""
    uid = generate_unique_id(prefix="test")

    assert uid.startswith("test-")
    assert len(uid) <= 63
    assert uid[0].isalnum()
    assert uid[-1].isalnum()
    assert re.match(r"^[a-z0-9][-a-z0-9]*[a-z0-9]$", uid)


def test_generate_unique_id_with_invalid_prefix_start():
    """Test generating unique ID when prefix starts with non-alphanumeric after processing."""
    # Use a prefix that starts with a character that will be converted to dash
    uid = generate_unique_id(prefix="---test")

    # Should start with 'p' prefix since processed prefix starts with non-alphanumeric
    assert uid.startswith("p-")
    assert len(uid) <= 63
    assert uid[0].isalnum()
    assert uid[-1].isalnum()
    assert re.match(r"^[a-z0-9][-a-z0-9]*[a-z0-9]$", uid)


def test_generate_unique_id_long_prefix():
    """Test generating unique ID with very long prefix."""
    # Create a long prefix that will cause truncation
    long_prefix = "a" * 60
    uid = generate_unique_id(prefix=long_prefix, max_length=63)

    assert len(uid) <= 63
    assert uid[0].isalnum()
    assert uid[-1].isalnum()
    assert re.match(r"^[a-z0-9][-a-z0-9]*[a-z0-9]$", uid)


def test_generate_unique_id_prefix_with_uppercase():
    """Test generating unique ID with uppercase letters in prefix."""
    uid = generate_unique_id(prefix="TestPrefix")

    # Should be converted to lowercase
    assert uid.startswith("testprefix-")
    assert len(uid) <= 63
    assert uid[0].isalnum()
    assert uid[-1].isalnum()
    assert re.match(r"^[a-z0-9][-a-z0-9]*[a-z0-9]$", uid)


def test_generate_unique_id_prefix_with_special_chars():
    """Test generating unique ID with special characters in prefix."""
    uid = generate_unique_id(prefix="test@#$prefix")

    # Special characters should be replaced with dashes
    assert "test" in uid
    assert "prefix" in uid
    assert len(uid) <= 63
    assert uid[0].isalnum()
    assert uid[-1].isalnum()
    assert re.match(r"^[a-z0-9][-a-z0-9]*[a-z0-9]$", uid)


def test_generate_unique_id_custom_max_length():
    """Test generating unique ID with custom max length."""
    uid = generate_unique_id(max_length=30)

    assert len(uid) <= 30
    assert uid[0].isalnum()
    assert uid[-1].isalnum()
    assert re.match(r"^[a-z0-9][-a-z0-9]*[a-z0-9]$", uid)


def test_generate_unique_id_uniqueness():
    """Test that generated IDs are unique."""
    uid1 = generate_unique_id()
    uid2 = generate_unique_id()

    assert uid1 != uid2
