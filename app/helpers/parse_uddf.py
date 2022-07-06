from lxml import etree

def parse_uddf(data):
  root = etree.fromstring(data)
  results = {}
  results['max_depth'] = root.find('MaxDepth', root.nsmap).text # meters
  results['date_dived'] = root.find('StartTime', root.nsmap).text
  results['start_air'] =root.find('StartPressure', root.nsmap).text #bar
  results['end_air'] = root.find('EndPressure', root.nsmap).text #bar
  results['dive_length'] = root.find('Duration', root.nsmap).text #bar
  results['water_temp'] = root.find('EndTemperature', root.nsmap).text #bar
  return results
