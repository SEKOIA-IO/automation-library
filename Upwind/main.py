from upwind import UpwindModule
from upwind.upwind_detections_connector import UpwindDetectionsConnector

if __name__ == "__main__":
    module = UpwindModule()
    module.register(UpwindDetectionsConnector, "upwind_detections_connector")
    module.run()
