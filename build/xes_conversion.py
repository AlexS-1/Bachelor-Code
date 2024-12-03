import json
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

def convert_json_to_xes(json_data, output_file):
    # Create the root XES element
    root = Element('log')
    root.set('xes.version', '1.0')
    root.set('xes.features', 'nested-attributes')
    root.set('xmlns', 'http://www.xes-standard.org/')

    # Group by file (caseID)
    grouped_data = {}
    for entry in json_data:
        case_id = entry['file']
        if case_id not in grouped_data:
            grouped_data[case_id] = []
        grouped_data[case_id].append(entry)

    # Create traces (cases)
    for case_id, events in grouped_data.items():
        trace = SubElement(root, 'trace')
        
        # Add caseID as attribute
        trace_string = SubElement(trace, 'string')
        trace_string.set('key', 'concept:name')
        trace_string.set('value', case_id)

        # Add events to the trace
        for event in events:
            event_element = SubElement(trace, 'event')
            
            # Add attributes for the event
            for key, value in event.items():
                if key == 'file':  # Skip the file as it's used as caseID
                    continue
                attr_type = 'string'
                if 'time' in key:
                    attr_type = 'date'  # Use date type for time fields
                event_attr = SubElement(event_element, attr_type)
                event_attr.set('key', key)
                event_attr.set('value', str(value))

    # Save the output
    xml_str = parseString(tostring(root)).toprettyxml(indent="  ")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(xml_str)
