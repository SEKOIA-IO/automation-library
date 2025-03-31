from sekoia_automation.action import GenericAPIAction

base_url = "api/v1/sic/"

PatchAlert = type(
    "PatchAlert",
    (GenericAPIAction,),
    {"verb": "patch", "endpoint": base_url + "alerts/{uuid}", "query_parameters": []},
)

TriggerActionOnAlertWorkflow = type(
    "TriggerActionOnAlertWorkflow",
    (GenericAPIAction,),
    {
        "verb": "patch",
        "endpoint": base_url + "alerts/{uuid}/workflow",
        "query_parameters": [],
    },
)

CreateNewIncident = type(
    "CreateNewIncident",
    (GenericAPIAction,),
    {"verb": "post", "endpoint": base_url + "incidents", "query_parameters": []},
)

ActivateCountermeasure = type(
    "ActivateCountermeasure",
    (GenericAPIAction,),
    {
        "verb": "patch",
        "endpoint": base_url + "alerts/countermeasures/{cm_uuid}/activate",
        "query_parameters": [],
    },
)

ListIncidents = type(
    "ListIncidents",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "incidents",
        "query_parameters": [
            "limit",
            "offset",
            "date[created_at]",
            "match[status_uuid]",
            "match[status_name]",
            "match[reference]",
            "match[community_uuid]",
            "sort",
            "direction",
        ],
    },
)

ListAlerts = type(
    "ListAlerts",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "alerts",
        "query_parameters": [
            "limit",
            "offset",
            "stix",
            "match[community_uuid]",
            "match[entity_name]",
            "match[entity_uuid]",
            "match[status_uuid]",
            "match[status_name]",
            "match[type_category]",
            "match[type_value]",
            "match[source]",
            "match[target]",
            "match[node]",
            "match[rule_uuid]",
            "match[rule_name]",
            "match[short_id]",
            "date[created_at]",
            "date[updated_at]",
            "range[urgency]",
            "sort",
            "direction",
        ],
    },
)

DenyCountermeasure = type(
    "DenyCountermeasure",
    (GenericAPIAction,),
    {
        "verb": "patch",
        "endpoint": base_url + "alerts/countermeasures/{cm_uuid}/deny",
        "query_parameters": [],
    },
)

GetIncident = type(
    "GetIncident",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "incidents/{incident_uuid}",
        "query_parameters": ["community_uuid"],
    },
)

PostCommentOnAlert = type(
    "PostCommentOnAlert",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "alerts/{uuid}/comments",
        "query_parameters": [],
    },
)


GetAlert = type(
    "GetAlert",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "alerts/{uuid}",
        "query_parameters": ["stix", "cases"],
    },
)

UpdateIncident = type(
    "UpdateIncident",
    (GenericAPIAction,),
    {
        "verb": "patch",
        "endpoint": base_url + "incidents/{incident_uuid}",
        "query_parameters": [],
    },
)

CreateNewBlock = type(
    "CreateNewBlock",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "incidents/{incident_uuid}/blocks",
        "query_parameters": ["object_refs", "community_uuid"],
    },
)

CreateCase = type(
    "CreateCase",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "cases",
        "query_parameters": [],
    },
)

ListsCases = type(
    "ListsCases",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "cases",
        "query_parameters": [
            "limit",
            "offset",
            "date[created_at]",
            "match[status_uuid]",
            "match[status_name]",
            "match[tags]",
            "match[assignees]",
            "match[created_by]",
            "match[community_uuid]",
            "sort",
            "direction",
        ],
    },
)

ListAllTags = type(
    "ListAllTags",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "cases/tags",
        "query_parameters": ["limit", "offset", "community_uuid"],
    },
)

GetCase = type(
    "GetCase",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "cases/{uuid}",
        "query_parameters": ["community_uuid"],
    },
)

UpdateCase = type(
    "UpdateCase",
    (GenericAPIAction,),
    {
        "verb": "patch",
        "endpoint": base_url + "cases/{uuid}",
        "query_parameters": [],
    },
)

DeleteCase = type(
    "DeleteCase",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": base_url + "cases/{case_uuid}",
        "query_parameters": [],
    },
)

AssociateNewAlertsOnCase = type(
    "AssociateNewAlertsOnCase",
    (GenericAPIAction,),
    {
        "verb": "patch",
        "endpoint": base_url + "cases/{case_uuid}/alerts",
        "query_parameters": [],
    },
)

ReplaceAssociatedAlertsToCase = type(
    "ReplaceAssociatedAlertsToCase",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "cases/{case_uuid}/alerts",
        "query_parameters": [],
    },
)


ListsAlertsAssociatedToCaseUuid = type(
    "ListsAlertsAssociatedToCaseUuid",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "cases/{case_uuid}/alerts",
        "query_parameters": [],
    },
)

RemoveEventFromCase = type(
    "RemoveEventFromCase",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": base_url + "cases/{case_uuid}/events/{event_id}",
        "query_parameters": [],
    },
)

PostCommentOnCase = type(
    "PostCommentOnCase",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "cases/{uuid}/comments",
        "query_parameters": [],
    },
)

GetListOfCommentsOfCase = type(
    "GetListOfCommentsOfCase",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "cases/{case_uuid}/comments",
        "query_parameters": [
            "limit",
            "offset",
            "date[created_at]",
            "match[created_by]",
            "sort",
            "direction",
        ],
    },
)

DeleteCommentFromCase = type(
    "DeleteCommentFromCase",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": base_url + "cases/{case_uuid}/comments/{comment_uuid}",
        "query_parameters": [],
    },
)

GetCommentOfCase = type(
    "GetCommentOfCase",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "cases/{case_uuid}/comments/{comment_uuid}",
        "query_parameters": [],
    },
)

UpdateCommentOfCase = type(
    "UpdateCommentOfCase",
    (GenericAPIAction,),
    {
        "verb": "patch",
        "endpoint": base_url + "cases/{case_uuid}/comments/{comment_uuid}",
        "query_parameters": [],
    },
)

AddEventsToACase = type(
    "AddEventsToACase",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "cases/{uuid}/events",
        "query_parameters": [],
    },
)

GetCustomStatus = type(
    "GetCustomStatus",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "custom_statuses/{status_uuid}",
        "query_parameters": [],
    },
)

GetCustomPriority = type(
    "GetCustomPriority",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "custom_priorities/{priority_uuid}",
        "query_parameters": [],
    },
)

GetCustomVerdict = type(
    "GetCustomVerdict",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "custom_verdicts/{verdict_uuid}",
        "query_parameters": [],
    },
)

assets_v1_base_url = "api/v1/asset-management/"
assets_v2_base_url = "api/v2/asset-management/"

ListTypesForAssets = type(
    "ListTypesForAssets",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": assets_v1_base_url + "asset-types",
        "query_parameters": [
            "match[uuid]",
            "match[name]",
            "match[category_name]",
            "match[category_uuid]",
            "limit",
            "offset",
        ],
    },
)

ReturnsTypeForAssets = type(
    "ReturnsTypeForAssets",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": assets_v1_base_url + "asset-types/{uuid}",
        "query_parameters": [],
    },
)

ListAssets = type(
    "ListAssets",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": assets_v2_base_url + "assets",
        "query_parameters": [
            "limit",
            "offset",
            "search",
            "uuids",
            "community_uuids",
            "type",
            "category",
            "source",
            "reviewed",
            "rule_uuid",
            "criticality",
            "rule_version",
            "sort",
            "direction",
        ],
    },
)

CreatesNewAsset = type(
    "CreatesNewAsset",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": assets_v1_base_url + "assets",
        "query_parameters": [],
    },
)

CreatesNewAssetV2 = type(
    "CreatesNewAssetV2",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": assets_v2_base_url + "assets",
        "query_parameters": [],
    },
)

DeletesAsset = type(
    "DeletesAsset",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": assets_v1_base_url + "assets/{uuid}",
        "query_parameters": [],
    },
)

DeletesAssetV2 = type(
    "DeletesAsset",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": assets_v2_base_url + "assets/{uuid}",
        "query_parameters": [],
    },
)

ReturnsAsset = type(
    "ReturnsAsset",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": assets_v1_base_url + "assets/{uuid}",
        "query_parameters": [],
    },
)

ListsAttributesOfAssets = type(
    "ListsAttributesOfAssets",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": assets_v1_base_url + "assets/{uuid}/attr",
        "query_parameters": ["limit", "offset"],
    },
)

AddsAttributeToAsset = type(
    "AddsAttributeToAsset",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": assets_v1_base_url + "assets/{uuid}/attr",
        "query_parameters": ["name", "value"],
    },
)

DeletesAttributeFromAsset = type(
    "DeletesAttributeFromAsset",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": assets_v1_base_url + "assets/{uuid}/attr/{attribute_uuid}",
        "query_parameters": [],
    },
)

ReturnsAttributeOfAsset = type(
    "ReturnsAttributeOfAsset",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": assets_v1_base_url + "assets/{uuid}/attr/{attribute_uuid}",
        "query_parameters": [],
    },
)

ListsKeysOfAssets = type(
    "ListsKeysOfAssets",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": assets_v1_base_url + "assets/{uuid}/keys",
        "query_parameters": ["limit", "offset"],
    },
)

AddsKeyToAsset = type(
    "AddsKeyToAsset",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": assets_v1_base_url + "assets/{uuid}/keys",
        "query_parameters": ["name", "value"],
    },
)

DeletesKeyFromAsset = type(
    "DeletesKeyFromAsset",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": assets_v1_base_url + "assets/{uuid}/keys/{key_uuid}",
        "query_parameters": [],
    },
)

ReturnsKeyOfAsset = type(
    "ReturnsKeyOfAsset",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": assets_v1_base_url + "assets/{uuid}/keys/{key_uuid}",
        "query_parameters": [],
    },
)

ListsOwnersOfAssets = type(
    "ListsOwnersOfAssets",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": assets_v1_base_url + "assets/{uuid}/owners",
        "query_parameters": ["limit", "offset"],
    },
)

AddsOwnersToAsset = type(
    "AddsOwnersToAsset",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": assets_v1_base_url + "assets/{uuid}/owners",
        "query_parameters": ["owners"],
    },
)

DeletesOwnerFromAsset = type(
    "DeletesOwnerFromAsset",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": assets_v1_base_url + "assets/{uuid}/owners/{owner_uuid}",
        "query_parameters": [],
    },
)

ListsNamesForKeysOfAsset = type(
    "ListsNamesForKeysOfAsset",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": assets_v1_base_url + "attribute-names",
        "query_parameters": ["category", "type", "limit", "offset"],
    },
)

ReturnsAttributeName = type(
    "ReturnsAttributeName",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": assets_v1_base_url + "attribute-names/{uuid}",
        "query_parameters": [],
    },
)

ListsCategoriesForAssets = type(
    "ListsCategoriesForAssets",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": assets_v1_base_url + "categories",
        "query_parameters": ["limit", "offset"],
    },
)

ReturnsCategoryForAssets = type(
    "ReturnsCategoryForAssets",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": assets_v1_base_url + "categories/{uuid}",
        "query_parameters": [],
    },
)

ReturnsCategoryTypeForAssets = type(
    "ReturnsCategoryTypeForAssets",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": assets_v1_base_url + "categories/{uuid}/types",
        "query_parameters": ["limit", "offset"],
    },
)

predict_base_url = "api/v1/predict/"

PredictStateOfAlert = type(
    "PredictStateOfAlert",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": predict_base_url + "alert",
        "query_parameters": [],
    },
)

GetCyberKillChainStage = type(
    "GetCyberKillChainStage",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "kill-chains/{uuid}",
        "query_parameters": [],
    },
)

CreateRule = type(
    "CreateRule",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "conf/rules-catalog/rules",
        "query_parameters": [],
    },
)

DeleteRule = type(
    "DeleteRule",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": base_url + "conf/rules-catalog/rules/{uuid}",
        "query_parameters": ["community_uuid"],
    },
)

DisableRule = type(
    "DisableRule",
    (GenericAPIAction,),
    {
        "verb": "put",
        "endpoint": base_url + "conf/rules-catalog/rules/{uuid}/disabled",
        "query_parameters": ["community_uuid"],
    },
)

EnableRule = type(
    "EnableRule",
    (GenericAPIAction,),
    {
        "verb": "put",
        "endpoint": base_url + "conf/rules-catalog/rules/{uuid}/enabled",
        "query_parameters": ["community_uuid"],
    },
)

GetRule = type(
    "GetRule",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "conf/rules-catalog/rules/{uuid}",
        "query_parameters": [],
    },
)

UpdateRule = type(
    "UpdateRule",
    (GenericAPIAction,),
    {
        "verb": "put",
        "endpoint": base_url + "conf/rules-catalog/rules/{uuid}",
        "query_parameters": [],
    },
)

GetIntake = type(
    "GetIntake",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "conf/intakes/{uuid}",
        "query_parameters": [],
    },
)

GetEntity = type(
    "GetEntity",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "conf/entities/{uuid}",
        "query_parameters": [],
    },
)
