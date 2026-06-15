"""Tests for azure_ad/base.py compatibility models and validators."""

import pytest

from azure_ad.base import (
    ApplicationArguments,
    CompatBaseModel,
    IdArguments,
    RequiredSingleUserArguments,
    RequiredTwoUserArguments,
    RequiredTwoUserArgumentsV2,
    SingleUserArguments,
)


class TestCompatBaseModel:
    """Test CompatBaseModel v1↔v2 compatibility layer."""

    def test_model_validate_with_simple_dict(self):
        """Test model_validate accepts a dict."""
        data = {"id": "test-id"}
        result = IdArguments.model_validate(data)
        assert result.id == "test-id"

    def test_model_validate_with_v2_kwargs(self):
        """Test model_validate gracefully ignores v2-style kwargs."""
        data = {"id": "test-id"}
        # These v2 kwargs should be silently ignored
        result = IdArguments.model_validate(
            data,
            strict=True,
            from_attributes=False,
            context={"key": "value"},
        )
        assert result.id == "test-id"

    def test_model_dump_basic(self):
        """Test model_dump returns a dict."""
        obj = IdArguments(id="test-id")
        result = obj.model_dump()
        assert isinstance(result, dict)
        assert result["id"] == "test-id"

    def test_model_dump_with_include(self):
        """Test model_dump with include parameter."""
        obj = SingleUserArguments(id="test-id", userPrincipalName="user@example.com")
        result = obj.model_dump(include={"id"})
        assert "id" in result
        assert result["id"] == "test-id"

    def test_model_dump_with_v2_only_kwargs(self):
        """Test model_dump filters out v2-only kwargs before calling dict()."""
        obj = IdArguments(id="test-id")
        # These v2-only kwargs should be filtered out, not causing TypeError
        result = obj.model_dump(
            mode="python",
            context={"key": "value"},
            round_trip=True,
            warnings=False,
            serialize_as_any=True,
        )
        assert isinstance(result, dict)
        assert result["id"] == "test-id"

    def test_model_dump_with_mixed_kwargs(self):
        """Test model_dump with both v1 and v2 kwargs."""
        obj = SingleUserArguments(
            id="test-id",
            userPrincipalName="user@example.com",
        )
        result = obj.model_dump(
            include={"id"},
            mode="python",  # v2-only
            context={"key": "value"},  # v2-only
        )
        assert "id" in result
        assert result["id"] == "test-id"


class TestApplicationArguments:
    """Test ApplicationArguments model."""

    def test_create_with_object_id(self):
        """Test creating ApplicationArguments with objectId."""
        app = ApplicationArguments(objectId="app-123")
        assert app.objectId == "app-123"

    def test_create_without_object_id(self):
        """Test creating ApplicationArguments without objectId (optional)."""
        app = ApplicationArguments()
        assert app.objectId is None


class TestSingleUserArguments:
    """Test SingleUserArguments model."""

    def test_create_with_id(self):
        """Test creating with id."""
        args = SingleUserArguments(id="user-123")
        assert args.id == "user-123"
        assert args.userPrincipalName is None

    def test_create_with_user_principal_name(self):
        """Test creating with userPrincipalName."""
        args = SingleUserArguments(userPrincipalName="user@example.com")
        assert args.userPrincipalName == "user@example.com"
        assert args.id is None

    def test_create_with_both(self):
        """Test creating with both id and userPrincipalName."""
        args = SingleUserArguments(
            id="user-123",
            userPrincipalName="user@example.com",
        )
        assert args.id == "user-123"
        assert args.userPrincipalName == "user@example.com"


class TestRequiredSingleUserArguments:
    """Test RequiredSingleUserArguments validator."""

    def test_valid_with_id(self):
        """Test validation passes with id."""
        args = RequiredSingleUserArguments(id="user-123")
        assert args.id == "user-123"

    def test_valid_with_user_principal_name(self):
        """Test validation passes with userPrincipalName."""
        args = RequiredSingleUserArguments(userPrincipalName="user@example.com")
        assert args.userPrincipalName == "user@example.com"

    def test_valid_with_both(self):
        """Test validation passes with both."""
        args = RequiredSingleUserArguments(
            id="user-123",
            userPrincipalName="user@example.com",
        )
        assert args.id == "user-123"
        assert args.userPrincipalName == "user@example.com"

    def test_invalid_without_both(self):
        """Test validation fails when neither id nor userPrincipalName is provided."""
        with pytest.raises(ValueError, match="'id' or 'userPrincipalName' should be specified"):
            RequiredSingleUserArguments()

    def test_invalid_with_empty_strings(self):
        """Test validation fails with empty strings."""
        with pytest.raises(ValueError, match="'id' or 'userPrincipalName' should be specified"):
            RequiredSingleUserArguments(id="", userPrincipalName="")


class TestRequiredTwoUserArguments:
    """Test RequiredTwoUserArguments validator."""

    def test_valid_with_id_and_password(self):
        """Test validation passes with id and userNewPassword."""
        args = RequiredTwoUserArguments(
            id="user-123",
            userNewPassword="NewPassword123!",
        )
        assert args.id == "user-123"
        assert args.userNewPassword == "NewPassword123!"

    def test_valid_with_user_principal_name_and_password(self):
        """Test validation passes with userPrincipalName and userNewPassword."""
        args = RequiredTwoUserArguments(
            userPrincipalName="user@example.com",
            userNewPassword="NewPassword123!",
        )
        assert args.userPrincipalName == "user@example.com"
        assert args.userNewPassword == "NewPassword123!"

    def test_invalid_without_password(self):
        """Test validation fails without userNewPassword."""
        with pytest.raises(ValueError, match="'userPrincipalName' and.*should be specified"):
            RequiredTwoUserArguments(id="user-123")

    def test_invalid_without_user_identifier(self):
        """Test validation fails without user identifier."""
        with pytest.raises(ValueError, match="'userPrincipalName' and.*should be specified"):
            RequiredTwoUserArguments(userNewPassword="NewPassword123!")

    def test_invalid_without_both(self):
        """Test validation fails without both user identifier and password."""
        with pytest.raises(ValueError, match="'userPrincipalName' and.*should be specified"):
            RequiredTwoUserArguments()


class TestRequiredTwoUserArgumentsV2:
    """Test RequiredTwoUserArgumentsV2 validator."""

    def test_valid_with_id_and_password(self):
        """Test validation passes with id and userNewPassword."""
        args = RequiredTwoUserArgumentsV2(
            id="user-123",
            userNewPassword="NewPassword123!",
        )
        assert args.id == "user-123"
        assert args.userNewPassword == "NewPassword123!"
        assert args.forceChangePasswordNextSignIn is True

    def test_valid_with_user_principal_name(self):
        """Test validation passes with userPrincipalName."""
        args = RequiredTwoUserArgumentsV2(userPrincipalName="user@example.com")
        assert args.userPrincipalName == "user@example.com"
        assert args.forceChangePasswordNextSignIn is True

    def test_valid_with_all_fields(self):
        """Test validation passes with all fields."""
        args = RequiredTwoUserArgumentsV2(
            id="user-123",
            userNewPassword="NewPassword123!",
            forceChangePasswordNextSignIn=False,
            forceChangePasswordNextSignInWithMfa=True,
        )
        assert args.id == "user-123"
        assert args.userNewPassword == "NewPassword123!"
        assert args.forceChangePasswordNextSignIn is False
        assert args.forceChangePasswordNextSignInWithMfa is True

    def test_invalid_without_user_identifier(self):
        """Test validation fails without user identifier."""
        with pytest.raises(ValueError, match="'id' or 'userPrincipalName' should be specified"):
            RequiredTwoUserArgumentsV2(userNewPassword="NewPassword123!")

    def test_invalid_without_any_identifier(self):
        """Test validation fails without any identifier."""
        with pytest.raises(ValueError, match="'id' or 'userPrincipalName' should be specified"):
            RequiredTwoUserArgumentsV2()
