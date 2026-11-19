from posixpath import join as urljoin

from sekoia_automation.action import Action

from onyphe.models import OnypheMD5Arguments
from onyphe.utils import get_with_paging


class OnypheMD5Action(Action):
    """
    Action to scan an MD5 hash with Onyphe
    """

    def run(self, arguments: OnypheMD5Arguments) -> dict:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        get_url: str = urljoin(url, "md5/" + arguments.md5)

        params = {"page": arguments.first_page}

        return get_with_paging(get_url, self.module.configuration, arguments.budget, params)
