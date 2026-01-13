"""
GoogleThreatIntelligenceThreatListToIOCCollectionTrigger - Auto-generated trigger
Generated from AKONIS Integration Standard v0.1.0
"""
import time
from traceback import format_exc
from cachetools import TTLCache
from pymisp import PyMISP, PyMISPError
from sekoia_automation.trigger import Trigger


class GoogleThreatIntelligenceThreatListToIOCCollectionTrigger(Trigger):
    """
    Trigger to retrieve events from GoogleThreatIntelligenceModule.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = None
        self.processed_events = TTLCache(
            maxsize=10000,
            ttl=604800
        )
    
    @property
    def sleep_time(self):
        """Get sleep time between polls."""
        return int(self.configuration.get("sleep_time", 300))
    
    def initialize_client(self):
        """Initialize API client."""
        try:
            self.client = PyMISP(
                url=self.module.configuration.get("google_threat_intelligence_url"),
                key=self.module.configuration.get("google_threat_intelligence_api_key"),
                ssl=False,
                debug=False,
            )
            self.log(message="Client initialized", level="info")
        except Exception as error:
            self.log(message=f"Failed to initialize client: {error}", level="error")
            raise
    
    def fetch_events(self):
        """
        Fetch events from API.
        
        Returns:
            List of events
        """
        try:
            self.log(message="Fetching events", level="info")
            
            # Call API
            events = self.client.search(
                controller="attributes",
                to_ids=1,
                pythonify=True,
            )
            
            self.log(message=f"Retrieved {len(events)} events", level="info")
            return events
        
        except PyMISPError as error:
            self.log(message=f"API error: {error}", level="error")
            raise
    
    def filter_new_events(self, events):
        """
        Filter out already processed events.
        
        Args:
            events: List of events
        
        Returns:
            List of new events
        """
        new_events = []
        for event in events:
            event_id = event.get("ioc_hash")
            if event_id and event_id not in self.processed_events:
                new_events.append(event)
                self.processed_events[event_id] = True
        
        self.log(message=f"Filtered to {len(new_events)} new events", level="info")
        return new_events
    
    def run(self):
        """Main trigger loop."""
        self.log(message="Starting trigger", level="info")
        
        try:
            self.initialize_client()
        except Exception as error:
            self.log(message=f"Failed to initialize: {error}", level="error")
            return
        
        while self.running:
            try:
                # Fetch events
                events = self.fetch_events()
                
                # Filter new events
                events = self.filter_new_events(events)
                
                if events:
                    # Process events (implement your logic here)
                    self.log(message=f"Processing {len(events)} events", level="info")
                
                # Sleep
                time.sleep(self.sleep_time)
            
            except KeyboardInterrupt:
                self.log(message="Trigger stopped by user", level="info")
                break
            
            except Exception as error:
                self.log(message=f"Error in loop: {error}", level="error")
                self.log(message=format_exc(), level="error")
                time.sleep(60)
        
        self.log(message="Trigger stopped", level="info")