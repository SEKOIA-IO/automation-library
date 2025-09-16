import pytest
from unittest.mock import Mock, patch
from aws_helpers.account_validator import AwsAccountValidator, AwsCredentialsError


class TestAwsAccountValidator:
    """Test cases for AwsAccountValidator class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.mock_module = Mock()
        self.mock_module.configuration = {
            "aws_access_key": "test_access_key",
            "aws_secret_access_key": "test_secret_key",
            "aws_region_name": "us-east-1",
        }
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

        # Create a mock exception class
        class MockNoSuchEntityException(Exception):
            pass

        mock_client.exceptions.NoSuchEntityException = MockNoSuchEntityException
        mock_client.get_login_profile.side_effect = MockNoSuchEntityException("NoSuchEntity error")
        mock_session.return_value.client.return_value = mock_client

        # Act & Assert
        with pytest.raises(AwsCredentialsError) as exc_info:
            self.validator.validate()

        assert "The AWS credentials are invalid or do not have the required permissions" in str(exc_info.value)
        assert "NoSuchEntity error" in str(exc_info.value)

    @patch("aws_helpers.account_validator.boto3.Session")
    def test_validate_service_failure_exception(self, mock_session):
        """Test validate method when ServiceFailureException is raised."""
        # Arrange
        mock_client = Mock()

        # Create a mock exception class
        class MockServiceFailureException(Exception):
            pass

        # Set up the exceptions namespace properly - make sure they're different classes
        class MockNoSuchEntityException(Exception):
            pass

        mock_client.exceptions.NoSuchEntityException = MockNoSuchEntityException
        mock_client.exceptions.ServiceFailureException = MockServiceFailureException
        mock_client.get_login_profile.side_effect = MockServiceFailureException("ServiceFailure error")
        mock_session.return_value.client.return_value = mock_client

        # Act & Assert
        with pytest.raises(AwsCredentialsError) as exc_info:
            self.validator.validate()

        assert "AWS service failure occurred during validation" in str(exc_info.value)
        assert "ServiceFailure error" in str(exc_info.value)

    @patch("aws_helpers.account_validator.boto3.Session")
    def test_validate_generic_exception(self, mock_session):
        """Test validate method when generic Exception is raised."""
        # Arrange
        mock_client = Mock()

        # Create a mock exception class that doesn't match the specific AWS exceptions
        class MockGenericException(Exception):
            pass

        mock_client.exceptions.NoSuchEntityException = MockGenericException
        mock_client.exceptions.ServiceFailureException = MockGenericException
        mock_client.get_login_profile.side_effect = Exception("Generic error")
        mock_session.return_value.client.return_value = mock_client

        # Act & Assert
        with pytest.raises(AwsCredentialsError) as exc_info:
            self.validator.validate()

        assert "An error occurred during AWS account validation" in str(exc_info.value)
        assert "Generic error" in str(exc_info.value)
