import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from sekoia_formatter_modules.action_format import (
    FormatAction,
    FormatArguments,
    FormatResponse,
)


class TestFormatArguments:
    """Test the FormatArguments model"""

    def test_valid_arguments(self):
        """Test creating valid FormatArguments"""
        args = FormatArguments(template="Hello {name}!", data={"name": "World"})
        assert args.template == "Hello {name}!"
        assert args.data == {"name": "World"}

    def test_empty_data(self):
        """Test with empty data dictionary"""
        args = FormatArguments(template="No variables", data={})
        assert args.template == "No variables"
        assert args.data == {}

    def test_complex_data_types(self):
        """Test with various data types in the data dictionary"""
        args = FormatArguments(
            template="Test",
            data={
                "string": "text",
                "number": 42,
                "float": 3.14,
                "bool": True,
                "none": None,
                "list": [1, 2, 3],
            },
        )
        assert len(args.data) == 6


class TestFormatResponse:
    """Test the FormatResponse model"""

    def test_valid_response(self):
        """Test creating valid FormatResponse"""
        response = FormatResponse(formatted_text="Hello World!")
        assert response.formatted_text == "Hello World!"

    def test_empty_response(self):
        """Test with empty formatted text"""
        response = FormatResponse(formatted_text="")
        assert response.formatted_text == ""


class TestFormatAction:
    """Test the FormatAction class"""

    @pytest.fixture
    def action(self, data_storage):
        """Create a FormatAction instance for testing"""
        action = FormatAction(data_path=data_storage)
        action.log = MagicMock()
        action.error = MagicMock()
        return action

    def test_simple_formatting(self, action):
        """Test basic string formatting"""
        arguments = FormatArguments(template="Hello {name}!", data={"name": "World"})
        result = action.run(arguments)

        # Result is returned as a dict by the Action base class
        assert isinstance(result, dict)
        assert result["formatted_text"] == "Hello World!"
        action.log.assert_called()

    def test_multiple_variables(self, action):
        """Test formatting with multiple variables"""
        arguments = FormatArguments(
            template="Hello {first} {last}, you are {age} years old!", data={"first": "John", "last": "Doe", "age": 30}
        )
        result = action.run(arguments)

        assert result["formatted_text"] == "Hello John Doe, you are 30 years old!"

    def test_no_variables(self, action):
        """Test template with no variables"""
        arguments = FormatArguments(template="This is a static text", data={})
        result = action.run(arguments)

        assert result["formatted_text"] == "This is a static text"

    def test_numeric_values(self, action):
        """Test formatting with numeric values"""
        arguments = FormatArguments(template="Count: {count}, Price: {price:.2f}", data={"count": 5, "price": 19.99})
        result = action.run(arguments)

        assert result["formatted_text"] == "Count: 5, Price: 19.99"

    def test_epoch_timestamp_conversion(self, action):
        """Test automatic conversion of epoch timestamps to datetime"""
        # Unix timestamp for 2024-01-01 00:00:00 UTC
        epoch = 1704067200
        arguments = FormatArguments(template="Date: {timestamp}", data={"timestamp": epoch})
        result = action.run(arguments)

        # Check that it contains datetime representation
        assert "2024" in result["formatted_text"] or "2023" in result["formatted_text"]

    def test_epoch_timestamp_with_formatting(self, action):
        """Test epoch timestamp conversion with datetime formatting"""
        epoch = 1704067200
        arguments = FormatArguments(template="Date: {timestamp:%Y-%m-%d}", data={"timestamp": epoch})
        result = action.run(arguments)

        # The date should be properly formatted
        assert result["formatted_text"].startswith("Date: 2024-") or result["formatted_text"].startswith("Date: 2023-")

    def test_small_number_not_converted(self, action):
        """Test that small numbers are not treated as epoch timestamps"""
        arguments = FormatArguments(template="Number: {num}", data={"num": 12345})
        result = action.run(arguments)

        assert result["formatted_text"] == "Number: 12345"

    def test_float_epoch_timestamp(self, action):
        """Test float epoch timestamp conversion"""
        epoch = 1704067200.5
        arguments = FormatArguments(template="Time: {timestamp}", data={"timestamp": epoch})
        result = action.run(arguments)

        # Should contain datetime representation
        assert "2024" in result["formatted_text"] or "2023" in result["formatted_text"]

    def test_invalid_epoch_timestamp(self, action):
        """Test handling of invalid epoch timestamp"""
        # Very large number that would cause datetime conversion to fail
        invalid_epoch = 99999999999999
        arguments = FormatArguments(template="Value: {val}", data={"val": invalid_epoch})
        result = action.run(arguments)

        # Should use the original value
        assert str(invalid_epoch) in result["formatted_text"]

    def test_missing_variable_error(self, action):
        """Test error handling when variable is missing from data"""
        arguments = FormatArguments(template="Hello {name}!", data={})
        result = action.run(arguments)

        # Error should be called due to KeyError
        action.error.assert_called()
        assert result is None

    def test_invalid_template_format(self, action):
        """Test error handling with invalid template format"""
        arguments = FormatArguments(template="Hello {name!", data={"name": "World"})  # Missing closing brace
        result = action.run(arguments)

        # Error should be called
        action.error.assert_called()
        assert result is None

    def test_mixed_data_types(self, action):
        """Test formatting with mixed data types"""
        arguments = FormatArguments(
            template="String: {s}, Int: {i}, Float: {f:.1f}, Bool: {b}",
            data={"s": "text", "i": 42, "f": 3.14159, "b": True},
        )
        result = action.run(arguments)

        assert result["formatted_text"] == "String: text, Int: 42, Float: 3.1, Bool: True"

    def test_special_characters_in_template(self, action):
        """Test template with special characters"""
        arguments = FormatArguments(
            template="Email: {email}, Symbol: {symbol}", data={"email": "test@example.com", "symbol": "$"}
        )
        result = action.run(arguments)

        assert result["formatted_text"] == "Email: test@example.com, Symbol: $"

    def test_unicode_characters(self, action):
        """Test formatting with unicode characters"""
        arguments = FormatArguments(
            template="Hello {name}! 你好 {greeting}", data={"name": "World", "greeting": "世界"}
        )
        result = action.run(arguments)

        assert result["formatted_text"] == "Hello World! 你好 世界"

    def test_empty_string_value(self, action):
        """Test formatting with empty string value"""
        arguments = FormatArguments(template="Name: '{name}'", data={"name": ""})
        result = action.run(arguments)

        assert result["formatted_text"] == "Name: ''"

    def test_none_value(self, action):
        """Test formatting with None value"""
        arguments = FormatArguments(template="Value: {val}", data={"val": None})
        result = action.run(arguments)

        assert result["formatted_text"] == "Value: None"

    def test_list_value(self, action):
        """Test formatting with list value"""
        arguments = FormatArguments(template="Items: {items}", data={"items": [1, 2, 3]})
        result = action.run(arguments)

        assert result["formatted_text"] == "Items: [1, 2, 3]"

    def test_dict_value(self, action):
        """Test formatting with dict value"""
        arguments = FormatArguments(template="Config: {config}", data={"config": {"key": "value"}})
        result = action.run(arguments)

        assert "key" in result["formatted_text"]
        assert "value" in result["formatted_text"]

    def test_repeated_variable(self, action):
        """Test template with same variable used multiple times"""
        arguments = FormatArguments(template="{name} said: '{name} is great!'", data={"name": "Alice"})
        result = action.run(arguments)

        assert result["formatted_text"] == "Alice said: 'Alice is great!'"

    def test_log_called_with_correct_message(self, action):
        """Test that log is called with appropriate messages"""
        arguments = FormatArguments(template="Test {var}", data={"var": "value"})
        action.run(arguments)

        # Check that log was called at least twice (start and success)
        assert action.log.call_count >= 2

    def test_multiline_template(self, action):
        """Test formatting with multiline template"""
        arguments = FormatArguments(
            template="Name: {name}\nAge: {age}\nCity: {city}", data={"name": "John", "age": 25, "city": "NYC"}
        )
        result = action.run(arguments)

        expected = "Name: John\nAge: 25\nCity: NYC"
        assert result["formatted_text"] == expected

    def test_format_specification(self, action):
        """Test various format specifications"""
        arguments = FormatArguments(
            template="Hex: {num:x}, Binary: {num:b}, Percentage: {ratio:.1%}", data={"num": 255, "ratio": 0.75}
        )
        result = action.run(arguments)

        assert result["formatted_text"] == "Hex: ff, Binary: 11111111, Percentage: 75.0%"

    def test_alignment_formatting(self, action):
        """Test text alignment formatting"""
        arguments = FormatArguments(
            template="Left: '{text:<10}' Right: '{text:>10}' Center: '{text:^10}'", data={"text": "Hi"}
        )
        result = action.run(arguments)

        assert "Left: 'Hi        '" in result["formatted_text"]
        assert "Right: '        Hi'" in result["formatted_text"]
        assert "Center: '    Hi    '" in result["formatted_text"]

    def test_zero_epoch_timestamp(self, action):
        """Test that 0 is not treated as epoch timestamp"""
        arguments = FormatArguments(template="Value: {val}", data={"val": 0})
        result = action.run(arguments)

        assert result["formatted_text"] == "Value: 0"

    def test_negative_number(self, action):
        """Test negative numbers are not treated as timestamps"""
        arguments = FormatArguments(template="Temperature: {temp}", data={"temp": -15})
        result = action.run(arguments)

        assert result["formatted_text"] == "Temperature: -15"

    def test_boolean_values(self, action):
        """Test formatting with boolean values"""
        arguments = FormatArguments(template="True: {t}, False: {f}", data={"t": True, "f": False})
        result = action.run(arguments)

        assert result["formatted_text"] == "True: True, False: False"

    def test_extra_data_variables(self, action):
        """Test that extra variables in data don't cause issues"""
        arguments = FormatArguments(
            template="Hello {name}!", data={"name": "World", "extra": "unused", "another": 123}
        )
        result = action.run(arguments)

        assert result["formatted_text"] == "Hello World!"

    def test_escape_braces(self, action):
        """Test escaping braces in template"""
        arguments = FormatArguments(
            template="Literal braces: {{not_a_variable}} but this is: {var}", data={"var": "value"}
        )
        result = action.run(arguments)

        assert result["formatted_text"] == "Literal braces: {not_a_variable} but this is: value"
