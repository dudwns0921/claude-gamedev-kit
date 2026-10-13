extends RefCounted
## Reads the balance table (xlsx). An xlsx is a zip of XML, so ZIPReader · XMLParser are enough.
##
## Column A is the name (a variable of Balance), column B the value. The other columns are for people and are not read.
## The header row is skipped by its shape (not an upper-case name with a number), whatever language it is in.
## Excel collects text in sharedStrings.xml and writes only an index in the cell — to find a name, that is read first.


## {name: float}. Empty if the file is missing or cannot be read because a save is in progress.
static func read(path: String) -> Dictionary:
	var out := {}
	var file := ProjectSettings.globalize_path(path)
	if not FileAccess.file_exists(file):
		return out
	var zip := ZIPReader.new()
	if zip.open(file) != OK:
		return out
	var names: PackedStringArray = zip.get_files()
	var shared: Array[String] = []
	if names.has("xl/sharedStrings.xml"):
		shared = _shared_strings(zip.read_file("xl/sharedStrings.xml"))
	var sheet := ""
	for n: String in names:
		if n.begins_with("xl/worksheets/sheet") and n.ends_with(".xml") and (sheet == "" or n < sheet):
			sheet = n
	if sheet != "":
		out = _rows(zip.read_file(sheet), shared)
	zip.close()
	return out


static func _shared_strings(bytes: PackedByteArray) -> Array[String]:
	var out: Array[String] = []
	var xml := XMLParser.new()
	if bytes.is_empty() or xml.open_buffer(bytes) != OK:
		return out
	var text := ""
	var in_t := false
	var phonetic := 0  # <rPh> is a phonetic run — not text
	while xml.read() == OK:
		match xml.get_node_type():
			XMLParser.NODE_ELEMENT:
				var tag := xml.get_node_name()
				if tag == "si":
					text = ""
					if xml.is_empty():
						out.append("")
				elif tag == "rPh" and not xml.is_empty():
					phonetic += 1
				elif tag == "t" and not xml.is_empty():
					in_t = true
			XMLParser.NODE_TEXT, XMLParser.NODE_CDATA:
				if in_t and phonetic == 0:
					text += xml.get_node_data()
			XMLParser.NODE_ELEMENT_END:
				var tag := xml.get_node_name()
				if tag == "t":
					in_t = false
				elif tag == "rPh":
					phonetic -= 1
				elif tag == "si":
					out.append(text.xml_unescape())
	return out


static func _rows(bytes: PackedByteArray, shared: Array[String]) -> Dictionary:
	var out := {}
	var xml := XMLParser.new()
	if bytes.is_empty() or xml.open_buffer(bytes) != OK:
		return out
	var name := ""      # column A of this row
	var value := ""     # column B of this row
	var column := ""
	var kind := ""
	var reading := false
	var text := ""
	while xml.read() == OK:
		match xml.get_node_type():
			XMLParser.NODE_ELEMENT:
				var tag := xml.get_node_name()
				if tag == "row":
					name = ""
					value = ""
				elif tag == "c":
					column = xml.get_named_attribute_value_safe("r").rstrip("0123456789")
					kind = xml.get_named_attribute_value_safe("t")
					text = ""
				elif (tag == "v" or tag == "t") and not xml.is_empty():
					reading = true
			XMLParser.NODE_TEXT, XMLParser.NODE_CDATA:
				if reading:
					text += xml.get_node_data()
			XMLParser.NODE_ELEMENT_END:
				var tag := xml.get_node_name()
				if tag == "v" or tag == "t":
					reading = false
				elif tag == "c":
					var cell := text.xml_unescape()
					if kind == "s" and cell.is_valid_int() and int(cell) < shared.size():
						cell = shared[int(cell)]
					if column == "A":
						name = cell.strip_edges()
					elif column == "B":
						value = cell.strip_edges()
				elif tag == "row":
					if name != "" and name == name.to_upper() and value.is_valid_float():
						out[name] = value.to_float()
	return out
