from misp.misp_to_stix import MISPToSTIXAction


def test_misp_to_stix(misp_event):
    action = MISPToSTIXAction()

    results = action.run({"event": misp_event})

    assert len(results["bundle"]["objects"]) == 11

    patterns = set()

    for sdo in results["bundle"]["objects"]:
        if sdo["type"] == "indicator":
            patterns.add(sdo["pattern"])

    assert patterns == {
        "[file:hashes.'sha256' = '7603ff14295c93bc1b73c6c0d74148c555337fb52b4104752ce0d2f5f6f2940d']",
        "[file:hashes.'sha256' = '5e08d513e3402640b4492c481f588877a33be51c68dc20f65eda2396232f1dc0']",
        "[file:hashes.'sha256' = '9f17da6a8d15ef891e7a18cfeecfd6ce2dfa17b3086df3e7e11b2009486c23c3']",
        "[file:hashes.'sha256' = '76c3a81789b8673e39c2e17b6cd04c8707016322dd1b6aee0278d8b0c3c1c36e']",
        "[file:hashes.'sha256' = 'd4a74735785dfbfd340064e834462258f9016097da8aa9f92f5fc843e2d22b34']",
        "[file:hashes.'sha256' = 'a9645b9208c4b75b51dee6cc02844342fe7aba184b1055cc0fcccd30e641be95']",
        "[file:hashes.'sha256' = '396587e0e59d771f3f90d601fe8230201d7e9497dcf482344f531ecbb9d6da84']",
        "[file:hashes.'sha256' = 'f47dad9e1c6bf06287993b129adea90fed9347262b4e7060a5bfeb0fd1da2a03']",
        "[file:hashes.'sha256' = '7cf5151c21e271989e6702405537e51ec6c7e097de943cfe1428f6f0cfed3cd9']",
        "[file:hashes.'sha256' = '1bdaa4b98aee67b7e3e46802b871671b38e632a87e316c22ac272a6bd5b8e282']",
    }
