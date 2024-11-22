from pm4py.objects.log.obj import EventLog, Trace, Event
from pm4py.objects.log.exporter.xes import exporter as xes_exporter
import json

def save_to_json(data, path):
    with open(path, 'w') as json_file:
        json.dump(data, json_file, indent=4)

def save_to_xes(data, path):
    log = EventLog()
    # Iterate over each element in the data
    for file, commits in data.items():
        # Create a trace for the file
        trace = Trace()
        trace.attributes["file"] = file
        for commit in commits:
            # Extract event attributes
            event = Event()
            event["timestamp"] = commit.get("timestamp")
            event["author"] = commit.get("author")
            event["change_type"] = commit.get("change_type")
            # Add the event to the trace
            trace.append(event)
        # Add the trace to the log
        log.append(trace)
    xes_exporter.apply(log, path)