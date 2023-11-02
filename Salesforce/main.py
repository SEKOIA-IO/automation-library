"""Entry point for the Salesforce connector."""

from salesforce import SalesforceModule
from salesforce.connector import SalesforceConnector

if __name__ == "__main__":
    module = SalesforceModule()
    module.register(SalesforceConnector, "salesforce")
    module.run()
