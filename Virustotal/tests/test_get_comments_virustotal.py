import requests_mock

from virustotal.action_virustotal_getcomments import VirusTotalGetCommentsAction

# get comments (comments/get)
comments_results: dict = {
    "response_code": 1,
    "verbose_msg": "Resource found, comments, if any, returned here",
    "resource": "13166fc9de263ee2c676430ae88e65040e10761c90e79347a2684476bc60e622",
    "comments": [
        {
            "date": "20120404132340",
            "comment": r"""[b]Bot Communication Details:[\/b]\nServer DNS Name: 67.230.163.30
                   Service Port: 80\nDirection Command User-Agent Host Connection
                   Pragma\nGET \/?0b72ab=huTK4N7k6G9718ze0NLa5%2BnM1NaHx9fXtqfeyr
                   FjiKSbxZ%2BmmqOjpqeXZqPPnpOhnda\nrpJ2bkpfLyZdk0MqokZNplofO5aKh
                   [... continues ...]""",
        },
        {"date": "20120404132122", "comment": "#fakeAV"},
        {
            "date": "20120404131639",
            "comment": r"""GET \/ury1007_8085.php?il41225lo=jeWqkqWocs3h1NDHi6Lcx56mlaqol
                   tnVmG5lWJbO0eWeuqZ6w4nN4aKjo6CgkqOkb6mrxL%2BZw8%2FJatXCqrOdmO3
                   S16mjl5eUnNbemcTJooLGicreoqOpp5eeZ2pgY26aoaOUjNih1NfW4aKjmefS0
                   HFiYmRrkuPnzaPGXtSYx6KepaWkopKopG9jaJ%2BiqJWamWWjicXd0tPc3qbjq
                   6hlYKXR4ebQ1MaZoNDC4dnX5eLUmpiVoKVj1d3Z0IzPpNnXnuPb6d%2Fm0ZKnp
                   pR1otCs5sbUyXPcz8aS HTTP\/1.1\nAccept: image\/gif, image\/jpeg
                   , image\/pjpeg, image\/pjpeg, application\/x-shockwave-flash,
                   application\/vnd.ms-excel, application\/vnd.ms-powerpoint,
                   [... continues ...]""",
        },
    ],
}


def test_virustotal_get_comments():
    vt: VirusTotalGetCommentsAction = VirusTotalGetCommentsAction()
    vt.module.configuration = {"apikey": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}

    with requests_mock.Mocker() as mock:
        mock.get(
            "https://www.virustotal.com/vtapi/v2/comments/get"
            "?apikey=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            "&resource=99017f6eebbac24f351415dd410d522d",
            json=comments_results,
        )

        results: dict = vt.run({"resource": "99017f6eebbac24f351415dd410d522d"})

        assert results == comments_results
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "GET"
        assert (
            history[0].url == "https://www.virustotal.com/vtapi/v2/comments/get"
            "?apikey=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            "&resource=99017f6eebbac24f351415dd410d522d"
        )
