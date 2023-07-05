from darktrace_modules import DarktraceModule
from darktrace_modules.threat_visualizer_log_trigger import ThreatVisualizerLogConnector

if __name__ == "__main__":
    module = DarktraceModule()
    module.register(ThreatVisualizerLogConnector, "darktrace_threat_visualizer_logs")
    module.run()
