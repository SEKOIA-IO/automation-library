from unittest.mock import Mock, patch

import pytest

from aws_helpers.account_validator import AwsAccountValidator
from aws_helpers.base import AWSConfiguration, AWSModule


class TestAwsAccountValidator:
    """Test cases for AwsAccountValidator class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.mock_module = AWSModule()
        self.mock_module.configuration = AWSConfiguration(
            aws_access_key="test_access_key",
            aws_secret_access_key="test_secret_key",
            aws_region_name="us-east-1",
        )
        self.validator = AwsAccountValidator()
        self.validator.module = self.mock_module

    @patch("aws_helpers.account_validator.boto3.Session")
    def test_validate_success(self, mock_session):
        """Test validate method when credentials are valid and get_login_profile succeeds."""
        # Arrange
        mock_client = Mock()
        mock_client.get_login_profile.return_value = {"LoginProfile": {"UserName": "test"}}
        mock_session.return_value.client.return_value = mock_client

        # Act
        result = self.validator.validate()

        # Assert
        assert result is True
        mock_session.assert_called_once_with(
            aws_access_key_id="test_access_key", aws_secret_access_key="test_secret_key", region_name="us-east-1"
        )
        mock_client.get_login_profile.assert_called_once()

    @patch("aws_helpers.account_validator.boto3.Session")
    def test_validate_no_such_entity_exception(self, mock_session):
        """Test validate method when NoSuchEntityException is raised."""
        # Arrange
        mock_client = Mock()

        # Create a mock exception class with NoSuchEntity in the name
        class MockNoSuchEntityException(Exception):
            pass

        mock_client.get_login_profile.side_effect = MockNoSuchEntityException("NoSuchEntity error")
        mock_session.return_value.client.return_value = mock_client

        # Mock the error method to track calls
        self.validator.error = Mock()

        # Act
        result = self.validator.validate()

        # Assert
        assert result is False
        self.validator.error.assert_called_once()
        error_message = self.validator.error.call_args[0][0]
        assert "The AWS credentials are invalid or do not have the required permissions" in error_message
        assert "NoSuchEntity error" in error_message

    @patch("aws_helpers.account_validator.boto3.Session")
    def test_validate_service_failure_exception(self, mock_session):
        """Test validate method when ServiceFailureException is raised."""
        # Arrange
        mock_client = Mock()

        # Create a mock exception class with ServiceFailure in the name
        class MockServiceFailureException(Exception):
            pass

        mock_client.get_login_profile.side_effect = MockServiceFailureException("ServiceFailure error")
        mock_session.return_value.client.return_value = mock_client

        # Mock the error method to track calls
        self.validator.error = Mock()

        # Act
        result = self.validator.validate()

        # Assert
        assert result is False
        self.validator.error.assert_called_once()
        error_message = self.validator.error.call_args[0][0]
        assert "AWS service failure occurred during validation" in error_message
        assert "ServiceFailure error" in error_message

    @patch("aws_helpers.account_validator.boto3.Session")
    def test_validate_generic_exception(self, mock_session):
        """Test validate method when generic Exception is raised."""
        # Arrange
        mock_client = Mock()

        # Create a generic exception that doesn't match the specific AWS exception patterns
        mock_client.get_login_profile.side_effect = Exception("Generic error")
        mock_session.return_value.client.return_value = mock_client

        # Mock the error method to track calls
        self.validator.error = Mock()

        # Act
        result = self.validator.validate()

        # Assert
        assert result is False
        self.validator.error.assert_called_once()
        error_message = self.validator.error.call_args[0][0]
        assert "An error occurred during AWS account validation" in error_message
        assert "Generic error" in error_message
