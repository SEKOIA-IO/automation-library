from crowdstrike_telemetry import CrowdStrikeTelemetryModule, CrowdStrikeTelemetryModuleConfig


def test_module_configuration(session_faker):
    aws_access_key_id = session_faker.word()
    aws_secret_access_key = session_faker.word()
    aws_region = session_faker.word()
    module = CrowdStrikeTelemetryModule()
    module.configuration = {
        "aws_access_key_id": aws_access_key_id,
        "aws_secret_access_key": aws_secret_access_key,
        "aws_region": aws_region,
    }

    assert isinstance(module.configuration, CrowdStrikeTelemetryModuleConfig)
    assert module.configuration.aws_access_key_id == aws_access_key_id
    assert module.configuration.aws_secret_access_key == aws_secret_access_key
    assert module.configuration.aws_region == aws_region
