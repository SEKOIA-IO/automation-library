from posixpath import join as urljoin

from sekoia_automation.action import Action

from onyphe.utils import get_arg_md5, get_with_paging


class OnypheMD5Action(Action):
    """
    Action to scan an MD5 hash with Onyphe
    """

    def run(self, arguments) -> dict:
        url: str = "https://www.onyphe.io/api/v2/simple/"
        md5 = get_arg_md5(arguments)
        get_url: str = urljoin(url, "md5/" + md5)

        budget = arguments.get("budget", 1)
        params = {"page": arguments.get("first_page", 1)}

        return get_with_paging(get_url, self.module.configuration, budget, params)
