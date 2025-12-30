from misp.misp_to_stix_converter import STIXConverter
from sekoia_automation.action import Action


class MISPToSTIXAction(Action):
    def run(self, arguments):
        converter = STIXConverter()

        return {"bundle": converter.convert(arguments["event"])}
