"""Tests for path utility functions."""

from sparkwheel.path_patterns import PathPatterns, find_references


class TestPathPatterns:
    """Test PathPatterns class."""

    def test_find_absolute_references_in_expression(self):
        """Test finding references in expression."""
        refs = PathPatterns.find_absolute_references("$some_func(@model::lr, @optimizer)")
        # The function returns IDs without the @ symbol
        assert "model::lr" in refs
        assert "optimizer" in refs

    def test_find_absolute_references_in_plain_text(self):
        """Test finding references returns empty for plain text."""
        refs = PathPatterns.find_absolute_references("plain text without references")
        assert refs == []

    def test_find_references_function(self):
        """Test find_references utility function."""
        # Test the wrapper function - returns IDs without @
        refs = find_references("$some_func(@model::lr)")
        assert "model::lr" in refs

    def test_find_references_empty_for_plain_text(self):
        """Test find_references returns empty for plain text."""
        refs = find_references("just plain text")
        assert refs == []
