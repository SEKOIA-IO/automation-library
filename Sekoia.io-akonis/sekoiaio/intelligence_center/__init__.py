from sekoia_automation.action import GenericAPIAction

base_url = "api/v2/inthreat/"

BundlesUploadBundleObjectsToInthreat = type(
    "BundlesUploadBundleObjectsToInthreat",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "bundles",
        "query_parameters": [],
    },
)

CollectionsListObjects = type(
    "CollectionsListObjects",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "collections/{feed_id}/objects",
        "query_parameters": ["match[type]", "cursor", "limit"],
    },
)

CollectionsListPatterns = type(
    "CollectionsListPatterns",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "collections/{feed_id}/patterns",
        "query_parameters": ["limit", "modified_after", "after_id", "include_revoked"],
    },
)

ContentProposalsListContentProposals = type(
    "ContentProposalsListContentProposals",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "content-proposals",
        "query_parameters": [
            "limit",
            "offset",
            "match[assigned_to]",
            "match[reviewer]",
            "match[status]",
            "match[source_ref]",
            "match[name]",
            "sort",
        ],
    },
)

ContentProposalsCreateContentProposal = type(
    "ContentProposalsCreateContentProposal",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "content-proposals",
        "query_parameters": [],
    },
)

ContentProposalsBulkRejectContentProposals = type(
    "ContentProposalsBulkRejectContentProposals",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": base_url + "content-proposals/bulk",
        "query_parameters": ["limit", "offset", "match[id]"],
    },
)

ContentProposalsBulkUpdateContentProposals = type(
    "ContentProposalsBulkUpdateContentProposals",
    (GenericAPIAction,),
    {
        "verb": "patch",
        "endpoint": base_url + "content-proposals/bulk",
        "query_parameters": ["limit", "offset", "match[id]"],
    },
)

ContentProposalsBulkMergeContentProposals = type(
    "ContentProposalsBulkMergeContentProposals",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "content-proposals/bulk/merge",
        "query_parameters": ["limit", "offset", "match[id]"],
    },
)

ContentProposalsGetContentProposal = type(
    "ContentProposalsGetContentProposal",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "content-proposals/{uuid}",
        "query_parameters": [],
    },
)

ContentProposalsRejectContentProposal = type(
    "ContentProposalsRejectContentProposal",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": base_url + "content-proposals/{uuid}",
        "query_parameters": [],
    },
)

ContentProposalsModifyContentProposal = type(
    "ContentProposalsModifyContentProposal",
    (GenericAPIAction,),
    {
        "verb": "patch",
        "endpoint": base_url + "content-proposals/{uuid}",
        "query_parameters": [],
    },
)

ContentProposalsMergeContentProposal = type(
    "ContentProposalsMergeContentProposal",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "content-proposals/{uuid}/merge",
        "query_parameters": [],
    },
)

ContentProposalsObjectsListMergeProposalObjectsThatHaveBeenModified = type(
    "ContentProposalsObjectsListMergeProposalObjectsThatHaveBeenModified",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "content-proposals/{uuid}/objects",
        "query_parameters": [
            "limit",
            "offset",
            "match[type]",
            "match[name]",
            "has_warnings",
        ],
    },
)

ContentProposalsObjectsAddNewObjectToContentProposal = type(
    "ContentProposalsObjectsAddNewObjectToContentProposal",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "content-proposals/{uuid}/objects",
        "query_parameters": [],
    },
)

ContentProposalsObjectsBulkCreateObjectsInProposal = type(
    "ContentProposalsObjectsBulkCreateObjectsInProposal",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "content-proposals/{uuid}/objects/bulk",
        "query_parameters": [],
    },
)

ContentProposalsObjectsBulkRemoveObjectsFromProposal = type(
    "ContentProposalsObjectsBulkRemoveObjectsFromProposal",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": base_url + "content-proposals/{uuid}/objects/bulk",
        "query_parameters": ["limit", "offset", "match[id]"],
    },
)

ContentProposalsObjectsSearchObjects = type(
    "ContentProposalsObjectsSearchObjects",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "content-proposals/{uuid}/objects/search",
        "query_parameters": [
            "limit",
            "offset",
            "term",
            "type",
            "fill_with_consolidated",
        ],
    },
)

ContentProposalsObjectsRetrieveObjectChanges = type(
    "ContentProposalsObjectsRetrieveObjectChanges",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "content-proposals/{uuid}/objects/{object_uuid}",
        "query_parameters": [],
    },
)

ContentProposalsObjectsRemoveObjectChangesFromContentProposal = type(
    "ContentProposalsObjectsRemoveObjectChangesFromContentProposal",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": base_url + "content-proposals/{uuid}/objects/{object_uuid}",
        "query_parameters": [],
    },
)

ContentProposalsObjectsUpdateSuggestedChangesToObject = type(
    "ContentProposalsObjectsUpdateSuggestedChangesToObject",
    (GenericAPIAction,),
    {
        "verb": "patch",
        "endpoint": base_url + "content-proposals/{uuid}/objects/{object_uuid}",
        "query_parameters": [],
    },
)

ContentProposalsObjectsRetrieveObservables = type(
    "ContentProposalsObjectsRetrieveObservables",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "content-proposals/{uuid}/objects/{object_uuid}/observables",
        "query_parameters": ["fill_with_consolidated"],
    },
)

ContentProposalsObjectsRetrieveRelationships = type(
    "ContentProposalsObjectsRetrieveRelationships",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "content-proposals/{uuid}/objects/{object_uuid}/relationships",
        "query_parameters": ["limit", "offset", "fill_with_consolidated"],
    },
)

ContentProposalsObjectsMarkObjectAsReviewed = type(
    "ContentProposalsObjectsMarkObjectAsReviewed",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "content-proposals/{uuid}/objects/{object_uuid}/reviewed",
        "query_parameters": ["is_reviewed"],
    },
)

ContentProposalsObjectsIgnoreWarning = type(
    "ContentProposalsObjectsIgnoreWarning",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "content-proposals/{uuid}/objects/{object_uuid}/warnings/{warning_id}/ignore",
        "query_parameters": [],
    },
)

ContentProposalsObjectsReconsiderWarningSwitchIgnoredToFalse = type(
    "ContentProposalsObjectsReconsiderWarningSwitchIgnoredToFalse",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "content-proposals/{uuid}/objects/{object_uuid}/warnings/{warning_id}/reconsider",
        "query_parameters": [],
    },
)

ContentProposalsObservablesListMergeProposalObservablesThatHaveBeenModified = type(
    "ContentProposalsObservablesListMergeProposalObservablesThatHaveBeenModified",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "content-proposals/{uuid}/observables",
        "query_parameters": ["limit", "offset"],
    },
)

ContentProposalsObservablesAddNewObservableToContentProposal = type(
    "ContentProposalsObservablesAddNewObservableToContentProposal",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "content-proposals/{uuid}/observables",
        "query_parameters": [],
    },
)

ContentProposalsObservablesBulkCreateObservablesInProposal = type(
    "ContentProposalsObservablesBulkCreateObservablesInProposal",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "content-proposals/{uuid}/observables/bulk",
        "query_parameters": [],
    },
)

ContentProposalsObservablesBulkRemoveObservablesFromProposal = type(
    "ContentProposalsObservablesBulkRemoveObservablesFromProposal",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": base_url + "content-proposals/{uuid}/observables/bulk",
        "query_parameters": ["limit", "offset", "match[id]"],
    },
)

ContentProposalsObservablesSearchObservables = type(
    "ContentProposalsObservablesSearchObservables",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "content-proposals/{uuid}/observables/search",
        "query_parameters": [
            "limit",
            "offset",
            "term",
            "type",
            "fill_with_consolidated",
        ],
    },
)

ContentProposalsObservablesRetrieveIndicators = type(
    "ContentProposalsObservablesRetrieveIndicators",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "content-proposals/{uuid}/observables/{object_uuid}/indicators",
        "query_parameters": ["fill_with_consolidated"],
    },
)

ContentProposalsObservablesRetrieveObservableChanges = type(
    "ContentProposalsObservablesRetrieveObservableChanges",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "content-proposals/{uuid}/observables/{observable_uuid}",
        "query_parameters": [],
    },
)

ContentProposalsObservablesRemoveObservableChangesFromContentProposal = type(
    "ContentProposalsObservablesRemoveObservableChangesFromContentProposal",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": base_url + "content-proposals/{uuid}/observables/{observable_uuid}",
        "query_parameters": [],
    },
)

ContentProposalsObservablesUpdateSuggestedChangesToObservable = type(
    "ContentProposalsObservablesUpdateSuggestedChangesToObservable",
    (GenericAPIAction,),
    {
        "verb": "patch",
        "endpoint": base_url + "content-proposals/{uuid}/observables/{observable_uuid}",
        "query_parameters": [],
    },
)

ContentProposalsObservablesMarkObservableAsReviewed = type(
    "ContentProposalsObservablesMarkObservableAsReviewed",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "content-proposals/{uuid}/observables/{observable_uuid}/reviewed",
        "query_parameters": ["is_reviewed"],
    },
)

ContentProposalsRelationshipsListMergeProposalRelationshipsThatHaveBeenModified = type(
    "ContentProposalsRelationshipsListMergeProposalRelationshipsThatHaveBeenModified",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "content-proposals/{uuid}/relationships",
        "query_parameters": ["limit", "offset"],
    },
)

ContentProposalsRelationshipsAddNewRelationshipToContentProposal = type(
    "ContentProposalsRelationshipsAddNewRelationshipToContentProposal",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "content-proposals/{uuid}/relationships",
        "query_parameters": [],
    },
)

ContentProposalsRelationshipsBulkCreateRelationshipsInProposal = type(
    "ContentProposalsRelationshipsBulkCreateRelationshipsInProposal",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "content-proposals/{uuid}/relationships/bulk",
        "query_parameters": [],
    },
)

ContentProposalsRelationshipsBulkRemoveRelationshipsFromProposal = type(
    "ContentProposalsRelationshipsBulkRemoveRelationshipsFromProposal",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": base_url + "content-proposals/{uuid}/relationships/bulk",
        "query_parameters": ["limit", "offset", "match[id]"],
    },
)

ContentProposalsRelationshipsRetrieveRelationshipChanges = type(
    "ContentProposalsRelationshipsRetrieveRelationshipChanges",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "content-proposals/{uuid}/relationships/{relationship_uuid}",
        "query_parameters": [],
    },
)

ContentProposalsRelationshipsRemoveRelationshipChangesFromContentProposal = type(
    "ContentProposalsRelationshipsRemoveRelationshipChangesFromContentProposal",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": base_url + "content-proposals/{uuid}/relationships/{relationship_uuid}",
        "query_parameters": [],
    },
)

ContentProposalsRelationshipsUpdateSuggestedChangesToRelationship = type(
    "ContentProposalsRelationshipsUpdateSuggestedChangesToRelationship",
    (GenericAPIAction,),
    {
        "verb": "patch",
        "endpoint": base_url + "content-proposals/{uuid}/relationships/{relationship_uuid}",
        "query_parameters": [],
    },
)

ContentProposalsRelationshipsMarkRelationshipAsReviewed = type(
    "ContentProposalsRelationshipsMarkRelationshipAsReviewed",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "content-proposals/{uuid}/relationships/{relationship_uuid}/reviewed",
        "query_parameters": ["is_reviewed"],
    },
)

ContentProposalsReopenContentProposal = type(
    "ContentProposalsReopenContentProposal",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "content-proposals/{uuid}/reopen",
        "query_parameters": [],
    },
)

ExpirationRulesListExpirationRules = type(
    "ExpirationRulesListExpirationRules",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "expiration-rules",
        "query_parameters": ["limit", "offset"],
    },
)

ExpirationRulesCreateNewExpirationRule = type(
    "ExpirationRulesCreateNewExpirationRule",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "expiration-rules",
        "query_parameters": [],
    },
)

ExpirationRulesGetExpirationRule = type(
    "ExpirationRulesGetExpirationRule",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "expiration-rules/{uuid}",
        "query_parameters": [],
    },
)

ExpirationRulesRemoveExpirationRule = type(
    "ExpirationRulesRemoveExpirationRule",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": base_url + "expiration-rules/{uuid}",
        "query_parameters": [],
    },
)

FeedsListFeeds = type(
    "FeedsListFeeds",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "feeds",
        "query_parameters": ["limit", "offset"],
    },
)

FeedsCreateNewFeed = type(
    "FeedsCreateNewFeed",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "feeds",
        "query_parameters": [],
    },
)

FeedsGetFeed = type(
    "FeedsGetFeed",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "feeds/{uuid}",
        "query_parameters": [],
    },
)

FeedsRemoveFeed = type(
    "FeedsRemoveFeed",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": base_url + "feeds/{uuid}",
        "query_parameters": [],
    },
)

PostImages = type(
    "PostImages",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "images/",
        "query_parameters": [],
    },
)

GetImagesName = type(
    "GetImagesName",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "images/{name}",
        "query_parameters": [],
    },
)

KillChainsListKillChains = type(
    "KillChainsListKillChains",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "kill-chains",
        "query_parameters": [],
    },
)

KillChainsGetKillChain = type(
    "KillChainsGetKillChain",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "kill-chains/{uuid}",
        "query_parameters": [],
    },
)

ObjectsListStixObjects = type(
    "ObjectsListStixObjects",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "objects",
        "query_parameters": [
            "limit",
            "offset",
            "match[type]",
            "match[subtype]",
            "match[tlp]",
            "match[source]",
        ],
    },
)

ObjectsCreateNewObject = type(
    "ObjectsCreateNewObject",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "objects",
        "query_parameters": [],
    },
)

ObjectsSearchObjects = type(
    "ObjectsSearchObjects",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "objects/search",
        "query_parameters": ["limit", "offset", "term"],
    },
)

GetObjectsObjectIdContext = type(
    "GetObjectsObjectIdContext",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "objects/{object_id}/context/",
        "query_parameters": ["community_uuid"],
    },
)

PostObjectsObjectIdFiles = type(
    "PostObjectsObjectIdFiles",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "objects/{object_id}/files/",
        "query_parameters": [],
    },
)

GetObjectsObjectIdFilesHash = type(
    "GetObjectsObjectIdFilesHash",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "objects/{object_id}/files/{hash}",
        "query_parameters": [],
    },
)

ObjectsGetObject = type(
    "ObjectsGetObject",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "objects/{uuid}",
        "query_parameters": [],
    },
)

ObjectsRevokeObject = type(
    "ObjectsRevokeObject",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": base_url + "objects/{uuid}",
        "query_parameters": [],
    },
)

ObjectsGetObjectDuplicates = type(
    "ObjectsGetObjectDuplicates",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "objects/{uuid}/duplicates",
        "query_parameters": ["limit", "offset"],
    },
)

ObjectsGetObjectNotesAndOpinions = type(
    "ObjectsGetObjectNotesAndOpinions",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "objects/{uuid}/notes",
        "query_parameters": ["limit", "offset"],
    },
)

ObjectsCreateNewNoteOrOpinion = type(
    "ObjectsCreateNewNoteOrOpinion",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "objects/{uuid}/notes",
        "query_parameters": [],
    },
)

ObjectsGetObjectsRelationships = type(
    "ObjectsGetObjectsRelationships",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "objects/{uuid}/relationships",
        "query_parameters": ["limit", "offset"],
    },
)

ObjectsGetObjectReports = type(
    "ObjectsGetObjectReports",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "objects/{uuid}/reports",
        "query_parameters": ["limit", "offset"],
    },
)

ObjectsGetObjectSources = type(
    "ObjectsGetObjectSources",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "objects/{uuid}/sources",
        "query_parameters": [],
    },
)

ObservableRelationshipsListObservablesRelationships = type(
    "ObservableRelationshipsListObservablesRelationships",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "observable-relationships",
        "query_parameters": ["limit", "offset"],
    },
)

ObservableRelationshipsCreateNewRelationship = type(
    "ObservableRelationshipsCreateNewRelationship",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "observable-relationships",
        "query_parameters": [],
    },
)

ObservableRelationshipsGetRelationship = type(
    "ObservableRelationshipsGetRelationship",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "observable-relationships/{uuid}",
        "query_parameters": [],
    },
)

ObservableRelationshipsRemoveRelationship = type(
    "ObservableRelationshipsRemoveRelationship",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": base_url + "observable-relationships/{uuid}",
        "query_parameters": [],
    },
)

ObservablesListObservables = type(
    "ObservablesListObservables",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "observables",
        "query_parameters": [
            "limit",
            "offset",
            "match[type]",
            "match[hash]",
            "match[name]",
            "match[value]",
            "match[tag]",
            "match[valid_tag]",
        ],
    },
)

ObservablesCreateNewObservable = type(
    "ObservablesCreateNewObservable",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "observables",
        "query_parameters": [],
    },
)

ObservablesUploadObservablesByBulk = type(
    "ObservablesUploadObservablesByBulk",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "observables/bulk",
        "query_parameters": [],
    },
)

ObservablesSearchObservables = type(
    "ObservablesSearchObservables",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "observables/search",
        "query_parameters": ["limit", "offset", "term"],
    },
)

ObservablesGetObservable = type(
    "ObservablesGetObservable",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "observables/{uuid}",
        "query_parameters": [],
    },
)

ObservablesGetObservableRelationships = type(
    "ObservablesGetObservableRelationships",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "observables/{uuid}/relationships",
        "query_parameters": ["limit", "offset"],
    },
)

ObservablesGetObservableReports = type(
    "ObservablesGetObservableReports",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "observables/{uuid}/reports",
        "query_parameters": ["limit", "offset"],
    },
)

RelationshipsListStixRelationships = type(
    "RelationshipsListStixRelationships",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "relationships",
        "query_parameters": ["limit", "offset"],
    },
)

RelationshipsCreateNewRelationship = type(
    "RelationshipsCreateNewRelationship",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "relationships",
        "query_parameters": [],
    },
)

RelationshipsGetRelationship = type(
    "RelationshipsGetRelationship",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "relationships/{uuid}",
        "query_parameters": [],
    },
)

RelationshipsRevokeRelationship = type(
    "RelationshipsRevokeRelationship",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": base_url + "relationships/{uuid}",
        "query_parameters": [],
    },
)

ReportsListStixReports = type(
    "ReportsListStixReports",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "reports",
        "query_parameters": ["limit", "offset"],
    },
)

PostReportsPdf = type(
    "PostReportsPdf",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "reports/pdf",
        "query_parameters": ["name", "source_ref"],
    },
)

PostReportsUrl = type(
    "PostReportsUrl",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "reports/url",
        "query_parameters": ["source_ref"],
    },
)

ReportsGetReport = type(
    "ReportsGetReport",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "reports/{uuid}",
        "query_parameters": [],
    },
)

ReportsGetReportObjects = type(
    "ReportsGetReportObjects",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "reports/{uuid}/objects",
        "query_parameters": ["limit", "offset"],
    },
)

ReportsGetReportObservables = type(
    "ReportsGetReportObservables",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "reports/{uuid}/observables",
        "query_parameters": ["limit", "offset"],
    },
)

SourcesListSources = type(
    "SourcesListSources",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "sources",
        "query_parameters": ["limit", "offset", "match[name]"],
    },
)

WarningRulesListWarningRules = type(
    "WarningRulesListWarningRules",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "warning-rules",
        "query_parameters": ["limit", "offset"],
    },
)

WarningRulesCreateNewWarningRule = type(
    "WarningRulesCreateNewWarningRule",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "warning-rules",
        "query_parameters": [],
    },
)

WarningRulesGetWarningRule = type(
    "WarningRulesGetWarningRule",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "warning-rules/{uuid}",
        "query_parameters": [],
    },
)

WarningRulesRemoveWarningRule = type(
    "WarningRulesRemoveWarningRule",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": base_url + "warning-rules/{uuid}",
        "query_parameters": [],
    },
)

ListTrackerNotifications = type(
    "ListTrackerNotifications",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "trackers/notifications/",
        "query_parameters": [
            "limit",
            "offset",
            "match[status]",
            "start",
            "end",
            "match[tracker_type]",
            "match[rule]",
            "match[ruleset_name]",
            "search",
        ],
    },
)


CreateNewTrackerNotification = type(
    "CreateNewTrackerNotification",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "trackers/notifications/",
        "query_parameters": [],
    },
)

GetTrackerNotification = type(
    "GetTrackerNotification",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "trackers/notifications/{uuid}",
        "query_parameters": [],
    },
)

ConvertNotificationIntoContentProposal = type(
    "ConvertNotificationIntoContentProposal",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "trackers/notifications/{uuid}/content-proposal",
        "query_parameters": ["auto_merge", "name", "enrich"],
    },
)

QualifyTrackerNotification = type(
    "QualifyTrackerNotification",
    (GenericAPIAction,),
    {
        "verb": "patch",
        "endpoint": base_url + "trackers/notifications/{uuid}/qualify/{status}",
        "query_parameters": [],
    },
)

ListTrackerRules = type(
    "ListTrackerRules",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "trackers/rules/",
        "query_parameters": ["limit", "offset", "match[name]", "match[ruleset_name]"],
    },
)
CreateNewTrackerRule = type(
    "CreateNewTrackerRule",
    (GenericAPIAction,),
    {
        "verb": "post",
        "endpoint": base_url + "trackers/rules/",
        "query_parameters": [],
    },
)

RemoveTrackerRule = type(
    "RemoveTrackerRule",
    (GenericAPIAction,),
    {
        "verb": "delete",
        "endpoint": base_url + "trackers/rules/{uuid}",
        "query_parameters": [],
    },
)

GetTrackerRule = type(
    "GetTrackerRule",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "trackers/rules/{uuid}",
        "query_parameters": [],
    },
)

GetTrackerRuleQuality = type(
    "GetTrackerRuleQuality",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "trackers/rules/{uuid}/quality",
        "query_parameters": [],
    },
)
