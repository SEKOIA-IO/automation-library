from easyvista_modules.action_base import EasyVistaAction, json_body
from easyvista_modules.models import DeleteRequestDocumentArguments


class DeleteRequestDocument(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = DeleteRequestDocumentArguments(**arguments)
        response = self.request("DELETE", self.request_path(args.rfc_number, "documents", args.id), check=False)
        if response is None:
            return None
        if response.status_code == 590:
            verification = self.request("GET", self.request_path(args.rfc_number, "documents"), check=False)
            data = json_body(verification) if verification is not None else None
            documents = data.get("Documents") if isinstance(data, dict) else None
            total_record_count = data.get("total_record_count") if isinstance(data, dict) else None
            if isinstance(total_record_count, str) and total_record_count.isdecimal():
                total_record_count = int(total_record_count)
            if (
                verification is not None
                and 200 <= verification.status_code < 300
                and isinstance(data, dict)
                and ("error" not in data)
                and isinstance(documents, list)
                and (not data.get("@next"))
                and (not (isinstance(total_record_count, int) and total_record_count > len(documents)))
                and all((isinstance(item, dict) and "DOCUMENT_ID" in item for item in documents))
                and (not any((str(item["DOCUMENT_ID"]) == args.id for item in documents)))
            ):
                error_data = json_body(response)
                error = (
                    str(error_data.get("error", error_data.get("message", self.response_error(response))))
                    if isinstance(error_data, dict)
                    else self.response_error(response)
                )
                error = self.redact(error)
                self.log(
                    level="warning",
                    message=f"EasyVista returned 590 ({error}) but document {args.id} is no longer attached "
                    f"to {args.rfc_number}: deletion confirmed",
                )
                return {
                    "success": True,
                    "status_code": 590,
                    "verified_by_listing": True,
                    "api_error": error,
                    "message": f"Document deleted (confirmed by listing; the API returned 590: {error})",
                }
            self._handle_response(response, suffix="; verification did not confirm the deletion")
            return None
        if not self._handle_response(response):
            return None
        return {
            "success": True,
            "status_code": response.status_code,
            "verified_by_listing": False,
            "message": "Document deleted",
        }
