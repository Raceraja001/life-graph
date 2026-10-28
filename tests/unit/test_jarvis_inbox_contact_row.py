from life_graph.services.jarvis_inbox import _first_phone, contact_row


def test_contact_row_with_all_fields():
    """Test contact_row with all fields present."""
    contact = {
        "id": "123",
        "name": "John Doe",
        "phones": ["+1 234 567 8900 (mobile)", "+1 234 567 8901 (home)"],
        "emails": ["john.doe@example.com", "johndoe@work.com"],
    }

    result = contact_row(contact)

    assert result["id"] == "123"
    assert result["name"] == "John Doe"
    assert result["phone"] == "+1 234 567 8900"
    assert result["email"] == "john.doe@example.com"


def test_contact_row_with_missing_fields():
    """Test contact_row with missing fields."""
    contact = {"id": "456", "name": "Jane Smith", "phones": [], "emails": []}

    result = contact_row(contact)

    assert result["id"] == "456"
    assert result["name"] == "Jane Smith"
    assert result["phone"] is None
    assert result["email"] is None


def test_first_phone_function():
    """Test _first_phone function with various phone formats."""
    # Test with valid phones
    phones = ["+1 234 567 8900 (mobile)", "+1 234 567 8901 (home)"]
    assert _first_phone(phones) == "+1 234 567 8900"

    # Test with empty list
    assert _first_phone([]) is None

    # Test with None
    assert _first_phone(None) is None

    # Test with phone without parentheses
    phones = ["+1 234 567 8900", "+1 234 567 8901"]
    assert _first_phone(phones) == "+1 234 567 8900"

    # Test with empty phone string
    phones = ["", "+1 234 567 8900"]
    assert _first_phone(phones) == "+1 234 567 8900"
