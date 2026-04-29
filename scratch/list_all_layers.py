import xml.etree.ElementTree as ET

tree = ET.parse("scratch/wfs_capabilities.xml")
root = tree.getroot()
namespaces = {'wfs': 'http://www.opengis.net/wfs', 'ows': 'http://www.opengis.net/ows'}
# Namespace handling in XML can be tricky, let's just find all Name tags
names = [elem.text for elem in tree.iter() if elem.tag.endswith('Name')]
print("All layers:", sorted(names))
