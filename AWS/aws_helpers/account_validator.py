import boto3
from sekoia_automation.account_validator import AccountValidator
from aws_helpers.base import AWSModule


class AwsCredentialsError(Exception):
    """Custom exception for AWS credential errors."""

    pass


class AwsAccountValidator(AccountValidator):
    module: AWSModule

    def client(self) -> boto3.client:
        session = boto3.Session(
            aws_access_key_id=self.module.configuration.aws_access_key,
            aws_secret_access_key=self.module.configuration.aws_secret_access_key,
            region_name=self.module.configuration.aws_region_name,
        )
        return session.client("iam")

    def validate(self) -> bool:
        try:
            client = self.client()
            client.get_login_profile()
            return True
        except client.exceptions.NoSuchEntityException as e:
            raise AwsCredentialsError(
                f"The AWS credentials are invalid or do not have the required permissions. Reason: {str(e)}"
            )
        except client.exceptions.ServiceFailureException as e:
            raise AwsCredentialsError(f"AWS service failure occurred during validation. Reason: {str(e)}")
        except Exception as e:
            raise AwsCredentialsError(f"An error occurred during AWS account validation: {str(e)}")
