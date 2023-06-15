from aws.utils import is_gzip_compressed, normalize_s3_key


def test_normalize_s3_key():
    # flake8: noqa
    assert (
        normalize_s3_key(
            "AWSLogs/111111111111/CloudTrail/eu-west-2/2022/02/21/111111111111_CloudTrail_eu-west-2_20220221T1020Z_nTGkKkyO0OcwEIvv.json.gz"
        )
        == "AWSLogs/111111111111/CloudTrail/eu-west-2/2022/02/21/111111111111_CloudTrail_eu-west-2_20220221T1020Z_nTGkKkyO0OcwEIvv.json.gz"
    )
    assert (
        normalize_s3_key(
            "AWSLogs/aws-account-id%3D111111111111/aws-service%3Dvpcflowlogs/aws-region%3Deu-west-3/year%3D2022/month%3D09/day%3D15/111111111111_vpcflowlogs_eu-west-3_fl-0f46d0a2ed744cfa1_20220915T1420Z_740b4cc6.log.parquet"
        )
        == "AWSLogs/aws-account-id=111111111111/aws-service=vpcflowlogs/aws-region=eu-west-3/year=2022/month=09/day=15/111111111111_vpcflowlogs_eu-west-3_fl-0f46d0a2ed744cfa1_20220915T1420Z_740b4cc6.log.parquet"
    )
    # flake8: qa


def test_is_gzip_compressed():
    gzip_content = b"\x1f\x8b\x08\x00\xaeC#c\x00\x03KT\xc8\xc9,)\xc9IU(I-.\xe1\x02\x009s\xc6\x83\x0e\x00\x00\x00"
    parquet_content = b"PAR1\x15\x04\x15\x08\x150\x15\xec\xfe\xff\x80\x0c<\x15\x02\x15\x04\x00\x00\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x00cbPAR1"
    assert is_gzip_compressed(b"") == False
    assert (
        is_gzip_compressed(
            parquet_content,
        )
        == False
    )
    assert (
        is_gzip_compressed(
            gzip_content,
        )
        == True
    )
