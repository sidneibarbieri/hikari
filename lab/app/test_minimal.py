from unittest.mock import patch
import pytest
import dummy_module

def test_dummy_function():
    with patch('dummy_module.dummy_function', return_value="Mocked Implementation"):
        assert dummy_module.dummy_function() == "Mocked Implementation"

