"""Exception hierarchy of WebRunner; every class derives from ``WebRunnerException``."""


class WebRunnerException(Exception):
    """Base class of every exception WebRunner raises itself."""


class WebRunnerWebDriverNotFoundException(WebRunnerException):
    """The requested browser name is not one WebRunner can start."""


class WebRunnerOptionsWrongTypeException(WebRunnerException):
    """The WebDriver options passed were not of the expected type."""


class WebRunnerArgumentWrongTypeException(WebRunnerException):
    """A browser argument passed to the options was not a string."""


class WebRunnerWebDriverIsNoneException(WebRunnerException):
    """A command needed a browser but none has been started."""


class WebRunnerExecuteException(WebRunnerException):
    """An action, an action list or the arguments of a run are not valid."""


# Json

class WebRunnerJsonException(WebRunnerException):
    """A JSON file could not be found, saved, parsed or reformatted."""


class WebRunnerGenerateJsonReportException(WebRunnerJsonException):
    """A report was asked for but there is no test record to build it from."""


class WebRunnerAssertException(WebRunnerException):
    """An assertion on a page, element or variable value did not hold."""


class WebRunnerHTMLException(WebRunnerException):
    """The HTML report could not be built from the data given."""


class WebRunnerAddCommandException(WebRunnerException):
    """A command could not be registered in the executor."""


# XML

class XMLException(WebRunnerException):
    """An XML document could not be read."""


class XMLTypeException(XMLException):
    """The XML source type asked for is not a supported one."""


class CallbackExecutorException(WebRunnerException):
    """The callback executor was given an unknown trigger function or callback argument mode."""


def describe_error(error: BaseException | None) -> str:
    """
    例外的一行描述，保證含訊息
    ``repr(error)``, unless that leaves the message out, as Selenium's exceptions do
    (``WebDriverException()``): then ``Type('message')``, with Selenium's ``msg`` (without
    its stack trace) as the message. ``None`` gives ``"None"``, as the test record expects.
    """
    text = repr(error)
    if error is None:
        return text
    message = error.msg if hasattr(error, "msg") else str(error).strip()  # Selenium's str() adds "Message: "
    if not message or str(message) in text:
        return text
    return f"{type(error).__name__}({str(message)!r})"
