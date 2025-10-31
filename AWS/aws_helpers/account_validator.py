import boto3
from sekoia_automation.account_validator import AccountValidator
from aws_helpers.base import AWSModule

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
        except Exception as e:
            # Check if it's a specific AWS exception by examining the exception type
            if hasattr(e, "__class__") and "NoSuchEntity" in e.__class__.__name__:
                self.error(f"The AWS credentials are invalid or do not have the required permissions. Reason: {str(e)}")
            elif hasattr(e, "__class__") and "ServiceFailure" in e.__class__.__name__:
                self.error(f"AWS service failure occurred during validation. Reason: {str(e)}")
            else:
                self.error(f"An error occurred during AWS account validation: {str(e)}")
            return False
