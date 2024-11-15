from glimps.base import GLIMPSAction
from glimps.models import ProfileStatus


class GetStatus(GLIMPSAction):
    """Action to retrieve profile status"""

    name = "Get profile status"
    description = "Get Glimps detect profile status, it includes quotas, eastimated analysis duration and cache"
    results_model = ProfileStatus

    def run(self, arguments) -> ProfileStatus:
        # send the request to Glimps
        status = self.gdetect_client.get_status()
        response = ProfileStatus(**status.to_dict())
        return response
