"""GraphQL queries of the Sophos Fusion APIs (Detections and tenant information).

The selection sets were checked against the schema of a Sophos Fusion tenant (introspection).
"""

TIMESTAMP = "{ seconds nanos }"

ENTITY_PROPERTIES = """
properties {
  __typename
  ... on EntityHost { host_id hostname hostname_fqdn computer_name mac_address os os_arch sensor_id sensor_type }
  ... on EntityUser { user_id user_name original_user_name domain_name auth_domain computer_name user_is_admin }
  ... on EntityIpAddress {
    ip_address ip_address_type ip_classification hostname is_nat_ip ip_geo_country_code ip_geo_city_name
  }
  ... on EntityProcess {
    process_id process_name process_image_path process_uuid process_correlation_id hash_md5 hash_sha1 hash_sha256
  }
  ... on EntityFile { file_name file_path file_size file_type hash_md5 hash_sha1 hash_sha256 }
  ... on EntityFileHash { hash_type hash_value }
  ... on EntityDomainName { domain_name }
  ... on EntityUrl { full_url uri_scheme uri_host uri_path uri_port }
  ... on EntityEmailAddress { email_address }
  ... on EntityAuthDomain { auth_domain }
  ... on EntityScript { script_name interpreter hash_value }
  ... on EntityRegistryKey { registry_path }
  ... on EntityService { service_name }
  ... on EntityScheduledTask { task_name }
}
"""

STRUCTURED_ENTITY = f"{{ id perspective identifiers display_name subtype {ENTITY_PROPERTIES} }}"

DETECTION_FIELDS = f"""
id
group_key
visibility
attack_technique_ids
parent_tenant_id
mdr_provider
suppressed
is_mdr
status
resolution_reason
tags
sensor_types
combined_username
threat_score
threat_score_v2
tenant {{ id name }}
metadata {{
  title
  full_title
  description
  severity
  confidence
  origin
  creator {{ detector {{ detector_id detector_name version }} rule {{ rule_id version }} }}
  engine {{ name version }}
  severity_updated_at {TIMESTAMP}
  began_at {TIMESTAMP}
  ended_at {TIMESTAMP}
  created_at {TIMESTAMP}
  inserted_at {TIMESTAMP}
  updated_at {TIMESTAMP}
  first_seen_at {TIMESTAMP}
}}
alerting_rules {{ id version }}
suppression_rules {{ id version }}
entities {{ entities relationships {{ from_entity to_entity relationship type }} }}
key_entities {{ entity label }}
source_entities {STRUCTURED_ENTITY}
target_entities {STRUCTURED_ENTITY}
event_ids {{ id }}
events_metadata {{
  began_at {TIMESTAMP}
  ended_at {TIMESTAMP}
  updated_at {TIMESTAMP}
  first_event_id
  last_event_id
  total_events
}}
enrichment_details {{
  mitre_attack_info {{ technique_id technique tactics url }}
  geo_ip {{ ip_address country_code_iso asn latitude longitude }}
  watchlist_matches {{ entity }}
}}
reference_details {{ reference {{ type url description }} }}
priority {{ value prioritizer }}
"""

ALERTS_RESPONSE = f"""
status
reason
search_id
alerts {{
  total_results
  next_offset
  total_parts
  part
  list {{ {DETECTION_FIELDS} }}
}}
"""

DETECTION_SEARCH = f"""
query DetectionSearch($in: SearchRequestInput) {{
  detectionSearch(in: $in) {{ {ALERTS_RESPONSE} }}
}}
"""

TENANT_MARKERS = """
query TenantMarkers($id: ID!) {
  tenant(id: $id) { id centralTenant { xdrOwnership hydrateTo } }
}
"""
