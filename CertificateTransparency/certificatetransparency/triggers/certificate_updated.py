import re

import certstream
from Levenshtein import distance
from sekoia_automation.trigger import Trigger


class CertificateUpdatedTrigger(Trigger):
    _ignoring: list[str] = ["email", "mail", "cloud"]

    _re_split: re.Pattern

    def run(self):
        self.log("Trigger starting")
        if len(self.configuration.get("keywords", [])) < 1:
            self.log(level="error", message="Missing keywords in trigger configuration.")
            return None

        extend_ignoring = self.configuration.get("ignoring", [])
        if len(extend_ignoring) > 0:
            self._ignoring.extend(extend_ignoring)

        self._re_split = re.compile(r"\W+")

        certstream.listen_for_events(self.analyse_domain, url="wss://certstream.calidog.io/")
        self.log("Trigger stopping")

    def analyse_domain(self, message, context):
        """Callback method for a new event"""

        if message["message_type"] == "certificate_update":
            for domain in message["data"]["leaf_cert"]["all_domains"]:
                matched_keyword = self._contains_keywords(domain)
                if matched_keyword:
                    self.send_event(
                        event_name=domain,
                        event={
                            "matched_keyword": matched_keyword,
                            "domain": domain,
                            "certstream_object": message["data"],
                        },
                    )

    def _contains_keywords(self, domain: str) -> str | bool:
        """
        Check if the domain contains a keyword or its derivations.

        :param domain: The domain to check.
        :return: The keyword matched, or false.
        """
        keywords: list[str] = self.configuration.get("keywords", None)
        max_distance = self.configuration.get("max_distance", 0)

        # match exact keyword in domain
        for word in keywords:
            if word in domain:
                return word

        if max_distance <= 0:
            return False

        words_in_domain = self._re_split.split(domain)

        # Testing Levenshtein distance for keywords
        for key in keywords:
            # Removing too generic words
            for word in [w for w in words_in_domain if w not in self._ignoring]:
                if distance(str(word), str(key)) <= max_distance:
                    return key

        return False
