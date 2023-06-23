import re

import certstream
import numpy
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

    def _levenshtein_distance(self, token1: str, token2: str) -> int:
        """Levenshtein distance is a calculation of the closeness of two works

        More precisely, it is the number of insertion/deletions/permutations
        required to go from a given word to another
        e.g. from "hello" to "jelly" the distance is 2 (j->h and o->y)
        See here for an explanation of how the algorithm works:
        https://blog.paperspace.com/measuring-text-similarity-using-levenshtein-distance/

        Args:
            token1 (str): First word to compare
            token2 (str): Second word to compare

        Returns:
            int: Levenshtein distance between token1 and token2
        """
        # Initialize a matrix of distances, where token1 is "the abscissa   "
        # and token2 is "the ordinate", so to say
        distances = numpy.zeros((len(token1) + 1, len(token2) + 1))
        # Variables used to store temp. distances later on
        a = 0
        b = 0
        c = 0

        # Fill the first line and column of the matrix with incremental values
        for t1 in range(len(token1) + 1):
            distances[t1][0] = t1
        for t2 in range(len(token2) + 1):
            distances[0][t2] = t2

        # We loop over each character of each token and see if they are identical
        for t1 in range(1, len(token1) + 1):
            for t2 in range(1, len(token2) + 1):
                # If so, the distance between the tokens doesn't increase:
                # we keep the previous value (i.e. the one 1 step earlier on the matrix's diagonale)
                if token1[t1 - 1] == token2[t2 - 1]:
                    distances[t1][t2] = distances[t1 - 1][t2 - 1]
                # Otherwise, we look up the distance of the previous steps, of which they are 3:
                # one char earlier on token1, on token2 or on both
                # We keep the lowest distance and increment it then add it to the matrix
                else:
                    a = distances[t1][t2 - 1]
                    b = distances[t1 - 1][t2]
                    c = distances[t1 - 1][t2 - 1]
                    distances[t1][t2] = min(a, b, c) + 1

        # Finally the actual distance is the low-right corner, the end of the diagonale
        return distances[len(token1)][len(token2)]

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
                if self._levenshtein_distance(str(word), str(key)) <= max_distance:
                    return key

        return False
