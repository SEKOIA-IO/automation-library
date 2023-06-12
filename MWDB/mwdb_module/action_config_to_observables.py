import uuid
from datetime import datetime

from sekoia_automation.action import Action

from mwdb_module.utils import datetime_to_str
from mwdb_module.extractors import JSONPathValueExtractor, SeparatedValueExtractor
from mwdb_module.model import MalwareRule
from mwdb_module.observables_from_config import ObservablesFromConfigForRule


class ConfigToObservablesAction(Action):
    MAPPING: dict[str, list[MalwareRule]] = {
        "amadey": [MalwareRule(type="domain-name", extractor=JSONPathValueExtractor("cncs[*].host"))],
        "avemaria": [MalwareRule(type="domain-name", extractor=JSONPathValueExtractor("c2[*].host"))],
        "agenttesla": [
            MalwareRule(type="email-addr", extractor=JSONPathValueExtractor("email")),
            MalwareRule(type="url", extractor=JSONPathValueExtractor("url")),
        ],
        "asyncrat": [
            MalwareRule(
                type="domain-name",
                extractor=JSONPathValueExtractor("domains[*].domain"),
                port_extractor=JSONPathValueExtractor("domains[*].port"),
            )
        ],
        "azorult": [MalwareRule(type="url", extractor=JSONPathValueExtractor("cnc"))],
        "brushaloader": [MalwareRule(type="url", extractor=JSONPathValueExtractor("url"))],
        "cobaltstrike": [
            MalwareRule(type="url", extractor=JSONPathValueExtractor("urls[*].url")),
            MalwareRule(
                type="domain-name",
                extractor=JSONPathValueExtractor("domains[*].domain"),
                global_port_extractor=JSONPathValueExtractor("Port"),
            ),
        ],
        "cryptbot": [
            MalwareRule(type="url", extractor=JSONPathValueExtractor("urls[*].url")),
            MalwareRule(
                type="domain-name",
                extractor=JSONPathValueExtractor("domains[*].domain"),
            ),
        ],
        "danabot": [
            MalwareRule(
                type="domain-name",
                extractor=JSONPathValueExtractor("urls[*]"),
                ignore_wrong_values=True,
            ),
            MalwareRule(type="ipv4-addr", extractor=JSONPathValueExtractor("ips[*].ip")),
            MalwareRule(type="url", extractor=JSONPathValueExtractor("urls[*].url")),
        ],
        "dbatloader": [
            MalwareRule(type="url", extractor=JSONPathValueExtractor("cncs[*].url")),
        ],
        "dharma": [
            MalwareRule(type="email-addr", extractor=JSONPathValueExtractor("emails[*]")),
        ],
        "dridex": [MalwareRule(type="domain-name", extractor=JSONPathValueExtractor("c2[*]"))],
        "emotet": [MalwareRule(type="domain-name", extractor=JSONPathValueExtractor("urls[*].cnc"))],
        "emotet_doc": [MalwareRule(type="url", extractor=JSONPathValueExtractor("urls[*]"))],
        "emotet_spam": [MalwareRule(type="domain-name", extractor=JSONPathValueExtractor("urls[*].cnc"))],
        "emotet_upnp": [MalwareRule(type="domain-name", extractor=JSONPathValueExtractor("urls[*].cnc"))],
        "evil-pony": [MalwareRule(type="url", extractor=JSONPathValueExtractor("urls[*].url"))],
        "formbook": [
            MalwareRule(
                type="url",
                extractor=JSONPathValueExtractor("urls[*].url"),
                protocol="http",
            )
        ],
        "get2": [MalwareRule(type="url", extractor=JSONPathValueExtractor("url"))],
        "gozi": [
            MalwareRule(
                type="domain-name",
                extractor=JSONPathValueExtractor("domains[*].domain"),
            )
        ],
        "guloader": [MalwareRule(type="url", extractor=JSONPathValueExtractor("urls[*].url"))],
        "hancitor": [MalwareRule(type="url", extractor=JSONPathValueExtractor("urls[*].url"))],
        "hawkeye": [MalwareRule(type="email-addr", extractor=JSONPathValueExtractor("EmailUsername"))],
        "icedid": [MalwareRule(type="domain-name", extractor=JSONPathValueExtractor("domains[*].cnc"))],
        "isfb": [
            MalwareRule(
                type="url",
                extractor=JSONPathValueExtractor("domains[*].cnc"),
                protocol="http",
            )
        ],
        "kpot": [MalwareRule(type="url", extractor=JSONPathValueExtractor("url[*]"))],
        "kronos": [
            MalwareRule(type="domain-name", extractor=JSONPathValueExtractor("cnc")),
            MalwareRule(type="url", extractor=JSONPathValueExtractor("urls[*].url")),
        ],
        "legionloader": [
            MalwareRule(type="url", extractor=JSONPathValueExtractor("stealer")),
            MalwareRule(type="url", extractor=JSONPathValueExtractor("cnc")),
            MalwareRule(type="url", extractor=JSONPathValueExtractor("drops[*]")),
        ],
        "lokibot": [MalwareRule(type="url", extractor=JSONPathValueExtractor("urls[*].url"))],
        "mirai": [
            MalwareRule(
                type="domain-name",
                extractor=JSONPathValueExtractor("cncs[*].host"),
                port_extractor=JSONPathValueExtractor("cncs[*].port"),
            ),
            MalwareRule(
                type="domain-name",
                extractor=JSONPathValueExtractor("domains[*].domain"),
                global_port_extractor=JSONPathValueExtractor("port"),
            ),
            MalwareRule(
                type="ipv4-addr",
                extractor=JSONPathValueExtractor("ips[*].ip"),
                global_port_extractor=JSONPathValueExtractor("port"),
            ),
        ],
        "nanocore": [
            MalwareRule(type="domain-name", extractor=JSONPathValueExtractor("Domain1")),
            MalwareRule(type="domain-name", extractor=JSONPathValueExtractor("Domain2")),
        ],
        "netwire": [
            MalwareRule(type="domain-name", extractor=JSONPathValueExtractor("urls[*].cnc")),
            MalwareRule(type="ipv4-addr", extractor=JSONPathValueExtractor("ips[*].ip")),
        ],
        "njrat": [
            MalwareRule(type="domain-name", extractor=JSONPathValueExtractor("c2[*]")),
            MalwareRule(
                type="domain-name",
                extractor=JSONPathValueExtractor("cncs[*].host"),
                port_extractor=JSONPathValueExtractor("cncs[*].port"),
            ),
        ],
        "orcusrat": [],  # For now nothing to extract but we can get related hashes
        "ostap": [MalwareRule(type="url", extractor=JSONPathValueExtractor("urls[*].url"))],
        "phorpiex": [
            MalwareRule(type="url", extractor=JSONPathValueExtractor("cnc_url")),
            MalwareRule(type="domain-name", extractor=JSONPathValueExtractor("cncs[*].host")),
        ],
        "pony": [
            MalwareRule(type="url", extractor=JSONPathValueExtractor("drops[*].url")),
            MalwareRule(type="url", extractor=JSONPathValueExtractor("urls[*].url")),
        ],
        "pushdo": [MalwareRule(type="domain-name", extractor=JSONPathValueExtractor("domains[*].cnc"))],
        "qakbot": [],  # For now nothing to extract but we can get related hashes
        "qbot": [
            MalwareRule(type="url", extractor=JSONPathValueExtractor("urls[*].url")),
            MalwareRule(type="domain-name", extractor=JSONPathValueExtractor("urls[*].url")),
        ],
        "quasar": [
            MalwareRule(type="url", extractor=JSONPathValueExtractor("urls[*].url")),
            MalwareRule(
                type="domain-name",
                extractor=JSONPathValueExtractor("urls[*].url"),
                port_extractor=JSONPathValueExtractor("urls[*].port"),
            ),
        ],
        "quasarrat": [MalwareRule(type="domain-name", extractor=JSONPathValueExtractor("hosts[*]"))],
        "raccoon": [MalwareRule(type="url", extractor=JSONPathValueExtractor("urls[*].url"))],
        "ramnit": [
            MalwareRule(
                type="domain-name",
                extractor=JSONPathValueExtractor("harcoded_domain[*]"),
            ),
            MalwareRule(
                type="domain-name",
                extractor=JSONPathValueExtractor("hardcoded_domain[*]"),
            ),
        ],
        "redline": [
            MalwareRule(
                type="url",
                extractor=JSONPathValueExtractor("urls[*].url"),
            )
        ],
        "redlinestealer": [
            MalwareRule(
                type="domain-name",
                extractor=JSONPathValueExtractor("cncs[*].host"),
                port_extractor=JSONPathValueExtractor("cncs[*].port"),
            )
        ],
        "remcos": [MalwareRule(type="domain-name", extractor=JSONPathValueExtractor("c2[*].host"))],
        "revengerat": [
            MalwareRule(
                type="domain-name",
                extractor=JSONPathValueExtractor("cncs[*].host"),
                port_extractor=JSONPathValueExtractor("cncs[*].port"),
            )
        ],
        "smokeloader": [MalwareRule(type="url", extractor=JSONPathValueExtractor("domains[*].cnc"))],
        "sodinokibi": [
            MalwareRule(
                type="domain-name",
                extractor=SeparatedValueExtractor("dmn", ";"),
            )
        ],
        "SquirrelWaffle": [MalwareRule(type="url", extractor=JSONPathValueExtractor("cncs[*].url"))],
        "systembc": [MalwareRule(type="domain-name", extractor=JSONPathValueExtractor("host[*]"))],
        "tofsee": [
            MalwareRule(
                type="domain-name",
                extractor=JSONPathValueExtractor("domains[*].domain"),
                port_extractor=JSONPathValueExtractor("domains[*].port"),
            )
        ],
        "trickbot": [
            MalwareRule(
                type="domain-name",
                extractor=JSONPathValueExtractor("urls[*].cnc"),
                port_extractor=JSONPathValueExtractor("urls[*].port"),
            )
        ],
        "valak": [MalwareRule(type="url", extractor=JSONPathValueExtractor("urls[*]"))],
        "vjworm": [MalwareRule(type="url", extractor=JSONPathValueExtractor("urls[*].url"))],
        "warzone": [
            MalwareRule(
                type="url",
                extractor=JSONPathValueExtractor("urls[*].url"),
            )
        ],
        "wshrat": [MalwareRule(type="url", extractor=JSONPathValueExtractor("c2[*]"))],
        "xloader": [
            MalwareRule(
                type="domain-name",
                extractor=JSONPathValueExtractor("domains[*].domain"),
            ),
            MalwareRule(
                type="url",
                extractor=JSONPathValueExtractor("urls[*].url"),
                decoys_extractor=JSONPathValueExtractor("decoy_domains[*].domain"),
            ),
        ],
        "zloader": [MalwareRule(type="url", extractor=JSONPathValueExtractor("urls[*].url"))],
    }

    HASH_MAPPING = {
        "ssdeep": "SSDEEP",
        "md5": "MD5",
        "sha1": "SHA-1",
        "sha256": "SHA-256",
        "sha512": "SHA-512",
    }

    def run(self, arguments: dict) -> dict:
        config = self.json_argument("config", arguments)

        observables = []
        if config["cfg"].get("type") in self.MAPPING:
            observables = self.extract_observables_from_config(config["cfg"])
        else:
            self.log(
                f"Type '{config['cfg'].get('type')}' is not handled by the action",
                level="warning",
            )

        observables += self.get_file_observables(config.get("files", []), config["cfg"].get("type"))
        bundle = {
            "type": "bundle",
            "id": f"bundle--{str(uuid.uuid4())}",
            "objects": observables,
        }
        return self.json_result("observables", bundle)

    def extract_observables_from_config(self, config: dict) -> list[dict]:
        observables = []
        for rule in self.MAPPING.get(config["type"], []):
            observables += ObservablesFromConfigForRule(rule, config).extract_observables()
        return observables

    def get_file_observables(self, files: list, config_type: str | None) -> list[dict]:
        observables = []
        for f in files:
            hashes = {algo: f[key] for key, algo in self.HASH_MAPPING.items() if key in f}
            if not hashes:
                continue
            tags = []
            if config_type:
                tags.append(
                    {
                        "name": config_type,
                        "valid_from": datetime_to_str(datetime.utcnow()),
                    }
                )

            observable = {
                "type": "file",
                "id": f"file--{str(uuid.uuid4())}",
                "hashes": hashes,
                "x_inthreat_tags": tags,
            }
            if "file_size" in f:
                observable["size"] = f["file_size"]
            observables.append(observable)
        return observables
