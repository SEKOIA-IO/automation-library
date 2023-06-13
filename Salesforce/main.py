"""Entry point for the Salesforce connector."""

from salesforce.connector import SalesforceConnector, SalesforceModule

if __name__ == "__main__":
    module = SalesforceModule()
    module.register(SalesforceConnector, "salesforce")
    module.run()
