"""Message texts for the exceptions of ``exceptions.py``."""

selenium_wrapper_web_driver_not_found_error = "WebDriver not found"  # pylint: disable=invalid-name  # public name

selenium_wrapper_set_options_error = "options must be a dict"  # pylint: disable=invalid-name  # public name
selenium_wrapper_set_argument_error = "argument must be a string"  # pylint: disable=invalid-name  # public name

executor_data_error = "executor received invalid data"  # pylint: disable=invalid-name  # public name
executor_list_error = (  # pylint: disable=invalid-name  # public name
    "executor received invalid data: list is empty or of wrong type"
)

# json
cant_find_json_error = "can't find JSON file"  # pylint: disable=invalid-name  # public name
cant_save_json_error = "can't save JSON file"  # pylint: disable=invalid-name  # public name
cant_reformat_json_error = "can't reformat JSON: is the type correct?"  # pylint: disable=invalid-name  # public name
cant_find_element_in_json_error = "can't find element in JSON"  # pylint: disable=invalid-name  # public name
json_type_error = "JSON type error"  # pylint: disable=invalid-name  # public name
wrong_json_data_error = "can't parse JSON"  # pylint: disable=invalid-name  # public name
cant_generate_json_report: str = "can't generate JSON report"  # pylint: disable=invalid-name  # public name

html_generate_no_data_tag = "can't generate HTML report: data is null"  # pylint: disable=invalid-name  # public name

# add command
add_command_exception_tag = (  # pylint: disable=invalid-name  # public name
    "command value type must be a method or function"
)

# argparse
argparse_get_wrong_data = "argparse received invalid data"  # pylint: disable=invalid-name  # public name

# XML
cant_read_xml_error: str = "can't read XML"  # pylint: disable=invalid-name  # public name
xml_type_error = "XML type error"  # pylint: disable=invalid-name  # public name

# Callback executor
get_bad_trigger_method: str = (  # pylint: disable=invalid-name  # public name
    "invalid trigger method: only kwargs and args accepted"
)
get_bad_trigger_function: str = (  # pylint: disable=invalid-name  # public name
    "invalid trigger function: only functions in event_dict accepted"
)
