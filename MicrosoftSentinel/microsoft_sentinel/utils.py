from typing import Dict, Any
from azure.mgmt.securityinsight.models import IncidentAdditionalData, IncidentOwnerInfo, IncidentLabel


def additional_data_to_dict(additional_data_item: IncidentAdditionalData) -> Dict[str, Any]:
    return {
        "additional_properties": additional_data_item.additional_properties,
        "alerts_count": additional_data_item.alerts_count,
        "bookmarks_count": additional_data_item.bookmarks_count,
        "comments_count": additional_data_item.comments_count,
        "alert_product_names": additional_data_item.alert_product_names,
        "tactics": additional_data_item.tactics,
    }


def owner_data_to_dict(incident_owner_item: IncidentOwnerInfo) -> Dict[str, Any]:
    return {
        "additional_properties": incident_owner_item.additional_properties,
        "assigned_to": incident_owner_item.assigned_to,
        "email": incident_owner_item.email,
        "user_principal_name": incident_owner_item.user_principal_name,
        "object_id": incident_owner_item.object_id,
    }


def labels_data_to_dict(label_item: IncidentLabel) -> Dict[str, Any]:
    return {
        "additional_properties": label_item.additional_properties,
        "label_name": label_item.label_name,
        "label_type": label_item.label_type,
    }
