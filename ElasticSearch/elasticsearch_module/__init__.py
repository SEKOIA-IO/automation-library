from abc import ABC
from functools import cached_property

from pydantic.v1 import BaseModel
from sekoia_automation.action import Action
from sekoia_automation.module import Module

from elasticsearch_module.client import ElasticSearchClient


class ElasticSearchConfiguration(BaseModel):
    url: str
    api_key: str
    disable_certificate_verification: bool | None = None
    sha256_tls_fingerprint: str | None = None


class ElasticSearchModule(Module):
    configuration: ElasticSearchConfiguration


class ElasticSearchAction(Action, ABC):
    module: ElasticSearchModule

    @cached_property
    def client(self):
        return ElasticSearchClient(
            url=self.module.configuration.url,
            api_key=self.module.configuration.api_key,
            disable_certificate_verification=self.module.configuration.disable_certificate_verification,
            sha256_tls_fingerprint=self.module.configuration.sha256_tls_fingerprint,
        )
