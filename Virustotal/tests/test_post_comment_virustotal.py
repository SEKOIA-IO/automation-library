import requests_mock

from virustotal.action_virustotal_postcomment import VirusTotalPostCommentAction

# post comment (comments/put)
comment_results: dict = {
    "response_code": 1,
    "verbose_msg": "Your comment was successfully posted",
}


def test_virustotal_post_comment():
    vt: VirusTotalPostCommentAction = VirusTotalPostCommentAction()
    vt.module.configuration = {"apikey": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}

    with requests_mock.Mocker() as mock:
        mock.post(
            "https://www.virustotal.com/vtapi/v2/comments/put"
            "?apikey=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            "&resource=99017f6eebbac24f351415dd410d522d"
            "&comment=Comment+test",
            json=comment_results,
        )

        results: dict = vt.run({"resource": "99017f6eebbac24f351415dd410d522d", "comment": "Comment test"})

        assert results == comment_results
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "POST"
        assert (
            history[0].url == "https://www.virustotal.com/vtapi/v2/comments/put"
            "?apikey=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            "&resource=99017f6eebbac24f351415dd410d522d"
            "&comment=Comment+test"
        )
