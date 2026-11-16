"""Source text of the executor scripts written into a generated project."""

executor_template_1: str = (  # pylint: disable=invalid-name  # public name
    """from je_web_runner import execute_action, read_action_json

execute_action(
    read_action_json(
        r"{temp}"
    )
)
"""
)

executor_template_2: str = (  # pylint: disable=invalid-name  # public name
    """from je_web_runner import execute_files, get_dir_files_as_list

execute_files(
    get_dir_files_as_list(
        r"{temp}"
    )
)
"""
)

bad_executor_template_1: str = (  # pylint: disable=invalid-name  # public name
    """
# This example is primarily intended to remind users of the importance of verifying input.
from je_web_runner import execute_action, read_action_json

execute_action(
    read_action_json(
        r"{temp}"
    )
)
"""
)
