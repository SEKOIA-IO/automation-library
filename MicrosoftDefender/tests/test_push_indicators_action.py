from copy import deepcopy
from datetime import datetime, timedelta

import requests_mock

from microsoftdefender_modules import MicrosoftDefenderModule
from microsoftdefender_modules.action_push_indicators import PushIndicatorsAction


def configured_action(action):
    module = MicrosoftDefenderModule()
    a = action(module=module)

    a.module.configuration = {
        "app_id": "test_app_id",
        "app_secret": "test_app_secret",
        "tenant_id": "test_tenant_id",
    }

    return a


STIX_OBJECT_IPv4 = {
    "valid_from": "2023-04-03T00:00:00Z",
    "x_ic_observable_types": ["ipv4-addr"],
    "created_by_ref": "identity--357447d7-9229-4ce1-b7fa-f1b83587048e",
    "object_marking_refs": ["marking-definition--f88d31f6-486f-44da-b317-01333bde0b82"],
    "type": "indicator",
    "name": "77.91.78.118",
    "pattern": "[ipv4-addr:value = '77.91.78.118']",
    "kill_chain_phases": [
        {"kill_chain_name": "lockheed-martin-cyber-kill-chain", "phase_name": "command-and-control"},
        {"kill_chain_name": "mitre-attack", "phase_name": "command-and-control"},
    ],
    "spec_version": "2.1",
    "x_ic_impacted_sectors": [
        "identity--f910fbcc-9f6a-43db-a6da-980c224ab2dd",
        "identity--ecc48a52-4495-4f19-bc26-5ee51c176816",
        "identity--7a486419-cd78-4fcf-845d-261539b05450",
        "identity--39746349-9c5c-47bd-8f39-0aff658d8ee7",
        "identity--337c119c-6436-4bd8-80a5-dcec9bad3b2d",
        "identity--41070ab8-3181-4c01-9f75-c11df5fb1ca3",
        "identity--0ecc1054-756c-47d5-b7d2-640e5ba96513",
        "identity--26f07f1b-1596-41c1-b23b-8efc5b105792",
        "identity--8e1db464-79dd-44d5-bc20-6b305d879674",
        "identity--063ef3d7-3989-4cf6-95ee-6217c0ab367a",
        "identity--02efd9e3-b685-4a9b-98a0-6b4800ff1143",
        "identity--3a6e8c1b-db90-4f81-a677-a57d0ee7f055",
        "identity--275946eb-0b8a-4ffc-9297-56f2275ef0d2",
        "identity--499a1938-8f6f-4023-82a1-56400e42d697",
        "identity--ce0be931-0e2e-4e07-864c-b9b169da5f15",
        "identity--98bc4ec8-590f-49bf-b51e-b37228b6a4c0",
        "identity--dde50644-38ad-414a-bb6e-e097123558b5",
        "identity--62b911a8-bcab-4f31-91f0-af9cdf9b6d20",
        "identity--333fecdb-e60d-46e4-9f21-5424dccef693",
        "identity--721280f7-6c79-4c72-8e6c-2a8b17c11b32",
        "identity--99b2746a-3ece-422c-aa6e-833fbc28ebd5",
        "identity--b48266ac-b1b8-4d85-bf09-a56dd0462a14",
        "identity--de6d2cda-d23b-47b5-a869-1065044aefe0",
        "identity--39729d0f-a13b-4b24-abbe-0912a135aee7",
        "identity--ec9d3a40-064c-4ec0-b678-85f5623fc4f1",
    ],
    "x_inthreat_sources_refs": ["identity--556006db-0d85-4ecb-8845-89d40ae0d40f"],
    "x_ic_is_in_flint": False,
    "pattern_type": "stix",
    "revoked": False,
    "confidence": 100,
    "valid_until": "2023-04-29T00:00:00Z",
    "created": "2023-04-03T11:35:32.984278Z",
    "lang": "en",
    "modified": "2023-04-19T09:03:46.063418Z",
    "x_ic_impacted_locations": [
        "location--d6e38bb4-9e11-443f-b4f1-dc53068e15c4",
        "location--ce895300-199f-44fc-b6ad-f69ee6305ef8",
        "location--c2a15f03-dfc1-4659-a553-87770d75657d",
        "location--b2f21856-d558-4904-bbe7-f832af1adc2a",
        "location--b1111318-86ad-41be-a876-fec7c5b30c99",
        "location--a5e214d3-3584-4a96-ba86-e4f9bb07d148",
        "location--9966148d-0992-4f36-a617-db3f73e178aa",
        "location--97a9a8ca-47f2-4015-9bcd-c87d87d2a8a1",
        "location--092a468b-54e1-4199-9737-7268c84115bd",
        "location--1175a3bd-dd53-4a7e-9cdd-50743079025a",
        "location--1719933e-1ce5-43f6-ac2f-e9318b194235",
        "location--60c65af5-26b6-4a74-a785-45388295b7d3",
        "location--01d5f74a-2417-4c8e-a799-4eda69ac64d0",
        "location--387542b5-5690-489f-8420-7f68b0b9b828",
        "location--a678bc81-d40c-4455-9242-501de8cd0b02",
        "location--369e8445-c3b9-49f3-8dc8-a8df793513f0",
        "location--82b6e924-7bd8-4e19-9685-6863196fc60f",
        "location--dea6cc03-a488-48cf-b09b-7e9ca7ad9f7c",
        "location--b9c12531-454c-44a9-8317-63a975993e11",
        "location--867d31af-0ae0-4738-ba86-6353a0e5fb01",
        "location--05eae806-132b-4ce9-a307-5352c2b27d51",
        "location--9671f7eb-5b14-485e-befd-6fc3bdb38366",
    ],
    "x_ic_deprecated": False,
    "id": "indicator--f24eb993-4ece-47ff-90e1-fa3f87de85dc",
    "indicator_types": ["malicious-activity"],
    "x_ic_external_refs": ["indicator--731e9ebf-1569-4f2d-8df2-f0bb048a8c70"],
}

STIX_OBJECT_FILE_HASH = {
    "lang": "en",
    "indicator_types": ["malicious-activity"],
    "kill_chain_phases": [
        {"phase_name": "installation", "kill_chain_name": "lockheed-martin-cyber-kill-chain"},
        {"phase_name": "persistence", "kill_chain_name": "mitre-attack"},
    ],
    "x_ic_observable_types": ["file"],
    "pattern": (
        "[file:hashes.'SHA-256' = '0451b9c358b1404717f5060aea5711327cf169cd4c5648f5ac23f1a1fb740716' "
        "OR file:hashes.MD5 = 'ab03a48a29967e738583140e6eb84f0b' "
        "OR file:hashes.'SHA-1' = 'f4db6264e2f9aa0aa1f889dd8cfaa886857c3bd0']"
    ),
    "object_marking_refs": ["marking-definition--613f2e26-407d-48c7-9eca-b8e91df99dc9"],
    "modified": "2023-04-19T15:00:57.176446Z",
    "valid_from": "2023-04-19T00:00:00Z",
    "created_by_ref": "identity--357447d7-9229-4ce1-b7fa-f1b83587048e",
    "pattern_type": "stix",
    "revoked": False,
    "x_ic_impacted_sectors": [
        "identity--f910fbcc-9f6a-43db-a6da-980c224ab2dd",
        "identity--f56e1adb-86d2-46a8-89f9-544ed0d8f6e2",
        "identity--ec9d3a40-064c-4ec0-b678-85f5623fc4f1",
        "identity--499a1938-8f6f-4023-82a1-56400e42d697",
        "identity--47ce715f-5c62-4991-8862-19efbb0a8dee",
        "identity--3dc8d72a-ce30-4846-af7b-431d1a4f9fd1",
        "identity--3a6e8c1b-db90-4f81-a677-a57d0ee7f055",
        "identity--3384b397-24c7-4935-8d33-e4970aa11298",
        "identity--39746349-9c5c-47bd-8f39-0aff658d8ee7",
        "identity--337c119c-6436-4bd8-80a5-dcec9bad3b2d",
        "identity--333fecdb-e60d-46e4-9f21-5424dccef693",
        "identity--0ecc1054-756c-47d5-b7d2-640e5ba96513",
        "identity--0f39d60f-f703-45e7-ace0-1fbbb583fb2c",
        "identity--cac0be1b-803d-4c41-aaa9-c9179f2aaff4",
        "identity--f29d78a1-dea7-4a86-af74-79fa19410907",
        "identity--3067ae6a-56f4-43b6-8cdf-3c41f8f5799f",
        "identity--d3ccd9b0-9961-475e-8899-43c41d20cce1",
        "identity--dde50644-38ad-414a-bb6e-e097123558b5",
        "identity--0429cd5f-7adc-48eb-9eac-461e86e6ec54",
        "identity--197fc617-c50c-421a-a73f-cb0cfedfe51f",
        "identity--5b6a9899-d0cd-4e09-8e73-4a60f88b8547",
        "identity--04ca1d36-bfd3-4150-860c-16fa85d14c6d",
        "identity--1c2ca424-60ca-4dfa-91e8-5231ae86f4e6",
        "identity--86488fc3-2973-4e62-b230-f6441f7d39f0",
        "identity--22c5f173-363a-4394-899d-8c2947d19507",
        "identity--0e2aa4de-d09e-4a77-9669-ec699af62089",
        "identity--7a486419-cd78-4fcf-845d-261539b05450",
        "identity--9aa7cd5f-9abb-44e9-9a39-fc559ab94158",
        "identity--39729d0f-a13b-4b24-abbe-0912a135aee7",
        "identity--b34cbcb2-4adc-4291-9909-21df1e40eec1",
        "identity--d4ee4ce4-0b99-4316-a00f-08afeeb68586",
        "identity--91ef3906-6821-4fa9-a75b-af7bf57da8c6",
        "identity--26f07f1b-1596-41c1-b23b-8efc5b105792",
        "identity--de6d2cda-d23b-47b5-a869-1065044aefe0",
        "identity--99b2746a-3ece-422c-aa6e-833fbc28ebd5",
        "identity--53779867-8f50-4e4b-afab-88fbbc6aa508",
        "identity--275946eb-0b8a-4ffc-9297-56f2275ef0d2",
        "identity--063ef3d7-3989-4cf6-95ee-6217c0ab367a",
        "identity--62b911a8-bcab-4f31-91f0-af9cdf9b6d20",
        "identity--ecc48a52-4495-4f19-bc26-5ee51c176816",
        "identity--98bc4ec8-590f-49bf-b51e-b37228b6a4c0",
        "identity--b5fcb38e-7e4c-436c-b443-2f5f8e522a53",
        "identity--6a7f7fbc-5485-42e5-a9da-b3bbc8137d21",
        "identity--41070ab8-3181-4c01-9f75-c11df5fb1ca3",
        "identity--b683566b-e6f0-406f-867a-3c3541cca886",
        "identity--7c5012dc-75c8-43e7-bf89-a3feb28e48b4",
        "identity--8e1db464-79dd-44d5-bc20-6b305d879674",
        "identity--b48266ac-b1b8-4d85-bf09-a56dd0462a14",
        "identity--c1371a50-ab86-4ddc-8a0f-2021be3dae63",
        "identity--db4a2f1a-9480-4dc7-92f5-88aafd6f83ba",
        "identity--c38472aa-9b41-471f-9110-2d1ff51b39f0",
        "identity--c42b7875-6d1f-4415-8b66-e998cb4355fb",
        "identity--ce0be931-0e2e-4e07-864c-b9b169da5f15",
        "identity--d8dfac5a-7d94-480e-abcc-c0a303bf26cd",
    ],
    "valid_until": "2024-04-15T00:00:00Z",
    "x_ic_impacted_locations": [
        "location--fcdc64b6-5791-4bb2-855d-15a414ce072f",
        "location--fb80e71b-2394-4344-a406-2ac98f0879f5",
        "location--fa9995b1-2f58-4ed1-83d0-89ae5e491a63",
        "location--f714e66f-f5f7-4ba2-8568-9f9e0811427d",
        "location--f2e5b076-45a1-4c4b-ae30-95f9970cee90",
        "location--ebd6f624-6ccb-429f-874d-dd4a343e0cef",
        "location--e9be5f61-2d42-4eb6-a158-13b1547c0045",
        "location--ddb9ac7a-8a0b-4790-a215-cb2e160d85a8",
        "location--da6c710a-eeb8-411a-9875-7524c63f5f94",
        "location--d6e38bb4-9e11-443f-b4f1-dc53068e15c4",
        "location--ce895300-199f-44fc-b6ad-f69ee6305ef8",
        "location--c2a15f03-dfc1-4659-a553-87770d75657d",
        "location--c23c9f9d-b72f-48d2-ad74-efa16c5135a1",
        "location--c1aceada-c5b5-40a6-9e19-5f01625f068a",
        "location--bbe350e1-6547-410b-8cce-5f91bc8c5068",
        "location--bbb8e2cd-a40e-4006-b315-abef26f81f41",
        "location--b9c12531-454c-44a9-8317-63a975993e11",
        "location--e9d38dd8-20b2-4e26-892a-9cb46bdc4d41",
        "location--b8664311-8c82-4606-a671-e30d95be5cee",
        "location--b6bd8dc3-d34b-49d6-8d7b-c205abca41a0",
        "location--b2f21856-d558-4904-bbe7-f832af1adc2a",
        "location--dea6cc03-a488-48cf-b09b-7e9ca7ad9f7c",
        "location--3bcb58ef-94e4-47c1-92d1-65e439c50e3f",
        "location--c58b9cf6-a29e-440c-ae3b-a3b842f5adbb",
        "location--7e9f431f-b99e-4f34-aa19-089aad3815ee",
        "location--bc9b90c5-be7b-483b-9e7f-15f4e4cbbbe3",
        "location--ae089f9f-4570-4171-8612-59a1e3133444",
        "location--4fcd8a70-7293-4681-bd72-255edc13c738",
        "location--dbebe2ba-c3c9-415a-91ef-2d9a0c83ce87",
        "location--4aac7d2a-42b8-4ff0-9cd2-081b500b0a2b",
        "location--21629cca-1177-4c52-8dd3-605372ed5600",
        "location--4390a589-27ad-497c-84bf-2a876bea06e2",
        "location--264fcf56-c597-4c84-be35-87510fa704a2",
        "location--3d56edf2-7a65-4c70-bcc6-f98864d1dee5",
        "location--3b8aada1-50a8-4a50-aa00-f7bc5aca5259",
        "location--5b52b395-79f9-4a75-b072-c8eb7be402da",
        "location--21c1247d-4234-48cf-86a6-b24b89cab7bd",
        "location--f73feb6e-5d1a-4ee8-9bc9-9a53c69928cb",
        "location--62decb69-71ae-49d3-8a1b-0189d78cad69",
        "location--66e9febd-33ca-4736-aec5-a9d9e13a6345",
        "location--35553bf8-64ae-4c3a-bc8c-ec4fffd65ed7",
        "location--0c074b83-cfe7-4b1d-bd11-18bbe0c39609",
        "location--867d31af-0ae0-4738-ba86-6353a0e5fb01",
        "location--34a19294-45f8-4664-9ea8-263002fe81d2",
        "location--c41ef74a-4292-47df-95f5-6f8ef7d2efb8",
        "location--b749a012-362f-43a0-aff7-171f9a0bedbc",
        "location--7aa2d1f9-0fb1-4181-8d4b-1b4d12858c30",
        "location--3423cede-cd5d-4878-a30b-a5cfe1b33096",
        "location--48636655-0643-488d-b4f0-dfb68a96cb8d",
        "location--9cdd3dae-449f-4111-a59a-779c88bf3099",
        "location--9d6b38f0-30ae-4ca3-b36d-79bd418ff382",
        "location--f16acf28-6181-4ec5-9821-712231a8c729",
        "location--0cbb95b5-06d0-4e09-aabc-2c8e8e640135",
        "location--4f5c2d10-5a9a-4c6e-b75e-216c74f365ba",
        "location--59fb0b50-8792-4ad7-abd1-c5b67311a315",
        "location--01d5f74a-2417-4c8e-a799-4eda69ac64d0",
        "location--10687ab6-8f6f-48c0-bd76-b1f0ad5502cc",
        "location--1175a3bd-dd53-4a7e-9cdd-50743079025a",
        "location--75614c0c-d8ea-4eb6-ab97-2d473da06f96",
        "location--7027490f-ab4d-4a66-ab41-5639a3ef666f",
        "location--8c5bf53a-8409-45c1-9d17-36e9df9355b1",
        "location--01a7bf2a-4bee-42bd-aac5-9f2b277ccd55",
        "location--a4e3db4d-364f-4407-bb63-8e15028cc3aa",
        "location--5b5cd168-59c8-45a0-ae61-8bdc7873b88c",
        "location--c10f2499-a30d-4192-b625-8dac29801910",
        "location--32682647-80fa-47ca-a364-8b8ab337d4ef",
        "location--03289a2f-a7af-475c-89b5-d071fcd80277",
        "location--69336d60-ce82-41b3-99c9-d73493a1a15e",
        "location--d2dc6c8d-c463-4872-8d43-08ca4bad5110",
        "location--369e8445-c3b9-49f3-8dc8-a8df793513f0",
        "location--092a468b-54e1-4199-9737-7268c84115bd",
        "location--a5e214d3-3584-4a96-ba86-e4f9bb07d148",
        "location--0363042f-05b9-42d7-b47e-7b9d04696bc2",
        "location--9671f7eb-5b14-485e-befd-6fc3bdb38366",
        "location--339d05db-907d-49a3-b699-de004149adb7",
        "location--457d7ea7-6965-463e-b739-f83912eda8f5",
        "location--10fbf417-71ad-4d61-a6c4-8ad40033432a",
        "location--62bb8e3e-7919-48e0-9608-c7569388d2c3",
        "location--1b39de90-a068-43da-9cdf-689aff1a1da1",
        "location--94f39acc-2999-4dcd-9f43-012d4f315f4b",
        "location--968ec102-a99f-4c94-85d0-f1a52227bd60",
        "location--984a1714-1dcb-42f8-b200-471850effa1d",
        "location--f5006be8-5dc6-489a-914a-4ba656f2df3e",
        "location--05eae806-132b-4ce9-a307-5352c2b27d51",
        "location--9e0b858a-2715-4d8e-b937-53707c48710f",
        "location--9f5eaaa6-bf4d-4371-b411-4c6da9f1fa98",
        "location--9966148d-0992-4f36-a617-db3f73e178aa",
        "location--150d4cad-d2fb-4344-af03-c5d8cdc10116",
        "location--3930b337-d8ed-4854-8832-da8cb412e150",
        "location--7efb98bd-8f7f-4a4e-9ca4-44f382705ce5",
        "location--1719933e-1ce5-43f6-ac2f-e9318b194235",
        "location--1e3ce2dd-6fb6-40a2-8dd2-d2310c64f5f0",
        "location--a5013209-3177-4642-90c5-9a3884717b4e",
        "location--52ded424-48e2-428d-8244-150b0afc6920",
        "location--079c1553-452c-4890-8341-1acecdcaf851",
        "location--ffa8eb57-0736-475a-ad11-623bb5a99fff",
        "location--53aabc6d-a513-4659-a82d-f064c2054cb1",
        "location--60c65af5-26b6-4a74-a785-45388295b7d3",
        "location--a06b3afd-e04c-4aaf-a8a2-b984ccbc8753",
        "location--af554517-cec1-44a8-af43-111b92b380c7",
        "location--66eb84d8-04ae-41f4-b4b7-3557aa8fd5a3",
        "location--68750320-c937-4395-8f4f-29d5ea7e028f",
        "location--23168672-6c82-491e-8da2-fb6c5721d04f",
        "location--6d02aae4-38b9-499b-9dea-d6818886ef8e",
        "location--387542b5-5690-489f-8420-7f68b0b9b828",
        "location--6ddedc37-60ae-48b9-afc9-96b640382165",
        "location--e54570c2-da38-4424-82f3-df8a89587c2b",
        "location--41e6f61f-d388-4317-b583-3d508b1d7776",
        "location--750b17e5-c1a0-4ef9-88ec-e0b6851d18f0",
        "location--d81eecc8-fc8e-4bed-8c28-25e79b5d2ba6",
        "location--79ead060-7b84-4a4a-a4cc-9eed380dd798",
        "location--814b1637-9888-4d42-b968-cc300e2e477e",
        "location--82b6e924-7bd8-4e19-9685-6863196fc60f",
        "location--97287f3b-07c2-4777-838b-d6cd00ebaccb",
        "location--c828b4b2-7847-4b03-8bc7-13f528df6099",
        "location--86a2a4c9-c5f4-4106-a64c-960c0d2d5e17",
        "location--8b65ff3b-2caf-4c96-a384-235b1bb2feda",
        "location--a7f5c36c-8808-4b22-b2f4-fa65ad00b1bc",
        "location--dcf747a4-f013-4f5c-924d-7226335e09f9",
        "location--8bb25232-5e69-4cd3-8991-9dab7abb25ff",
        "location--171d89d4-9b71-4a81-b47f-e75fd62df4fb",
        "location--17a894ea-dbb4-403d-baa7-bbd7d93aa97e",
        "location--97a9a8ca-47f2-4015-9bcd-c87d87d2a8a1",
        "location--2f1865d4-5f10-4a06-a45c-c6c8a3e5d053",
        "location--97ccd734-9ab2-4022-8809-fea8e8b4b7fd",
        "location--98d8b0e0-9d65-4019-a0f1-f9b435adc5d5",
        "location--27444b14-8e5b-45ba-8665-cab7ea46a70e",
        "location--9d781941-4a8b-4b52-86b5-4162057c91f4",
        "location--b1111318-86ad-41be-a876-fec7c5b30c99",
        "location--58797005-647b-4fe7-b261-33160e292a99",
        "location--a047aae7-4090-4d7e-af51-52b5979c545f",
        "location--9de733a6-1fed-4254-8aa5-c6c1262e8615",
        "location--99225dd7-8311-4a2e-8d82-4859aed0f48b",
        "location--9ef79c7e-473a-444b-95e1-8285b80aa28e",
        "location--a4528ad8-ccd8-4261-a110-12165800f479",
        "location--a678bc81-d40c-4455-9242-501de8cd0b02",
    ],
    "type": "indicator",
    "name": (
        "[file:hashes.'SHA-256' = '0451b9c358b1404717f5060aea5711327cf169cd4c5648f5ac23f1a1fb740716' "
        "OR file:hashes.MD5 = 'ab03a48a29967e738583140e6eb84f0b' "
        "OR file:hashes.'SHA-1' = 'f4db6264e2f9aa0aa1f889dd8cfaa886857c3bd0']"
    ),
    "confidence": 70,
    "x_ic_is_in_flint": False,
    "x_inthreat_sources_refs": ["identity--d0644ccd-4ce2-4fb2-9165-dc7860e42984"],
    "x_ic_deprecated": False,
    "spec_version": "2.1",
    "created": "2023-04-19T15:00:57.17643Z",
    "id": "indicator--8c28aed8-8370-46d5-b7bf-877e6a4840d3",
    "x_ic_external_refs": ["indicator--99048ce7-4cb0-4ac9-a28b-c2738fcd39be"],
}


def test_push_indicators():
    action = configured_action(PushIndicatorsAction)

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock.register_uri(
            "POST",
            "https://api.securitycenter.microsoft.com/api/indicators/import",
            json={
                "@odata.context": "https://api.securitycenter.microsoft.com/api/$metadata#Collection(microsoft.windowsDefenderATP.api.ImportIndicatorResult)",
                "value": [
                    {
                        "id": "1",
                        "indicator": "220e7d15b011d7fac48f2bd61114db1022197f7f",
                        "isFailed": False,
                        "failureReason": None,
                    },
                    {
                        "id": "2",
                        "indicator": "2233223322332233223322332233223322332233223322332233223322332222",
                        "isFailed": False,
                        "failureReason": None,
                    },
                ],
            },
        )

        results = action.run(
            {
                "stix_objects": [STIX_OBJECT_IPv4, STIX_OBJECT_FILE_HASH],
                "severity": "Medium",
                "action": "Warn",
                "generate_alert": False,
            }
        )
        assert results is None


def test_expired_indicators():
    action = configured_action(PushIndicatorsAction)

    arguments = {
        "severity": "Medium",
        "action": "Warn",
        "generate_alert": False,
        "valid_for": 1,
    }

    indicators = action.get_valid_indicators([STIX_OBJECT_IPv4, STIX_OBJECT_FILE_HASH], arguments)
    assert len(indicators["expired"]) == 2
    assert len(indicators["valid"]) == 0

    expiration_in_the_future = "%sZ" % (datetime.utcnow() + timedelta(days=1)).isoformat()

    STIX_OBJECT_IPv4_2 = deepcopy(STIX_OBJECT_IPv4)
    STIX_OBJECT_IPv4_2["valid_until"] = expiration_in_the_future

    STIX_OBJECT_FILE_HASH_2 = deepcopy(STIX_OBJECT_FILE_HASH)
    STIX_OBJECT_FILE_HASH_2["valid_until"] = expiration_in_the_future

    indicators = action.get_valid_indicators([STIX_OBJECT_IPv4_2, STIX_OBJECT_FILE_HASH_2], arguments)
    assert len(indicators["expired"]) == 0
    assert len(indicators["valid"]) == 2
