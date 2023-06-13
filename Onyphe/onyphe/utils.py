import ipaddress
import re

import requests
from requests import Response

from onyphe.errors import InvalidArgument, MissingAPIkey


def get_arg_ip(arguments):
    try:
        ip = arguments["ip"]
    except KeyError:
        raise TypeError("Missing required 'ip' argument")

    if not isinstance(ip, str):
        raise InvalidArgument(arg_type="IP", value=ip, value_type=type(ip))

    try:
        ipaddress.ip_address(ip)
    except ValueError:
        raise InvalidArgument(arg_type="IP", value=ip, value_type=type(ip))

    return ip


def get_arg_domain(arguments):
    try:
        domain = arguments["domain"]
    except KeyError:
        raise TypeError("Missing required 'domain' argument")

    if not isinstance(domain, str):
        raise InvalidArgument(arg_type="domain", value=domain, value_type=type(domain))

    domain = domain.lower()  # Onyphe returns 404 on GOOGLE.COM

    if len(domain) <= 253 and re.fullmatch(r"(?:[^.]{0,63}\.){1,127}[^.]{1,63}", domain):
        # up to 253 chars, up to 127 sublevels of length up to 63
        return domain
    else:
        raise InvalidArgument(arg_type="domain", value=domain, value_type=type(domain))


def get_arg_md5(arguments):
    try:
        md5 = arguments["md5"]
    except KeyError:
        raise TypeError("Missing required 'md5' argument")

    if not isinstance(md5, str):
        raise InvalidArgument(arg_type="md5", value=md5, value_type=type(md5))

    md5 = md5.lower()

    if re.fullmatch(r"[0-9a-f]{32}", md5):
        return md5
    else:
        raise InvalidArgument(arg_type="md5", value=md5, value_type=type(md5))


def get_arg_onion(arguments):
    try:
        onion = arguments["onion"]
    except KeyError:
        raise TypeError("Missing required 'onion' argument")

    if not isinstance(onion, str):
        raise InvalidArgument(arg_type="onion address", value=onion, value_type=type(onion))

    onion = onion.lower()

    if re.fullmatch(r"[2-7a-z]{16}(?:[2-7a-z]{40})?\.onion", onion):
        # 16 or 56 base32 characters followed by .onion
        return onion
    else:
        raise InvalidArgument(arg_type="onion address", value=onion, value_type=type(onion))


def get_with_paging(url: str, module_conf: dict, budget: int = 1, params: dict | None = None):
    if params is None:
        params = {}

    apikey = module_conf.get("apikey")
    if apikey is None:
        # any endpoint with paging requires an API key
        raise MissingAPIkey()

    params["apikey"] = apikey

    aggregated_result: dict = {}

    nbr_requests = 0
    max_pages = params.get("page", 1)
    while (
        aggregated_result.get("error", 0) == 0  # no Onyphe error occurred
        and (nbr_requests < budget or budget == 0)  # we are still under budget (or there is no budget limit)
        and params.get("page", 1) <= max_pages  # we did not exhaust all pages
    ):
        try:
            response: Response = requests.get(url, params=params)
        except requests.exceptions.RequestException as e:
            if aggregated_result.get("count", 0) == 0:
                raise e
            else:
                aggregated_result["error"] = -1  # I guess Onyphe does not use negative error codes
                aggregated_result["message"] = repr(e)
                break

        if response.status_code != 200:
            if aggregated_result.get("count", 0) == 0:
                response.raise_for_status()
            else:
                try:  # response.json() may contain more info
                    response_json = response.json()
                except ValueError:
                    response_json = {}

                aggregated_result["error"] = response_json.get("error") or -1
                aggregated_result["message"] = response_json.get("message") or (
                    str(response.status_code) + " " + response.reason
                )
                break

        try:
            response_json = response.json()
        except ValueError as e:
            if aggregated_result.get("count", 0) == 0:
                raise e
            else:
                aggregated_result["error"] = -1  # I guess Onyphe does not use negative error codes
                aggregated_result["message"] = repr(e)
                break

        aggregate_results(aggregated_result, response_json)
        nbr_requests += 1
        params["page"] = params.get("page", 1) + 1
        max_pages = aggregated_result.get("max_page", 0)

    if aggregated_result["error"]:
        aggregated_result["status"] = "nok"

    return aggregated_result


def aggregate_results(aggregated_result: dict, new_result: dict):
    aggregated_result["count"] = aggregated_result.get("count", 0) + new_result.get("count", 0)
    error_code = new_result.get("error", 0)
    aggregated_result["error"] = error_code
    if error_code:
        aggregated_result["message"] = new_result.get("message", "")
    aggregated_result["myip"] = new_result.get("myip", "")
    aggregated_result["results"] = aggregated_result.get("results", []) + new_result.get("results", [])
    aggregated_result["status"] = new_result.get("status", "nok")
    aggregated_result["took"] = f'{float(aggregated_result.get("took", "0")) + float(new_result.get("took", 0)):.3f}'
    aggregated_result["total"] = max(aggregated_result.get("total", 0), new_result.get("total", 0))
    aggregated_result["max_page"] = max(aggregated_result.get("max_page", 1), new_result.get("max_page", 1))
    aggregated_result["page"] = max(aggregated_result.get("page", 1), new_result.get("page", 1))
