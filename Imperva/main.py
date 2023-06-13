from sekoia_automation.module import Module

from imperva.fetch_logs import LogsDownloader

if __name__ == "__main__":
    module = Module()

    module.register(LogsDownloader, name="imperva_logs")

    module.run()
