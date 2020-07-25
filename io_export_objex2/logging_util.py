import logging

logging_trace_level = 5
logging.addLevelName(logging_trace_level, 'TRACE')

def getLogger(name):
    global root_logger
    log = root_logger.getChild(name)
    def trace(message, *args, **kws):
        if log.isEnabledFor(logging_trace_level):
            log._log(logging_trace_level, message, args, **kws)
    log.trace = trace
    def Logger_makeRecordWrapper(name, level, fn, lno, msg, args, exc_info, func=None, extra=None, sinfo=None):
        self = log
        record = logging.Logger.makeRecord(self, name, level, fn, lno, msg, args, exc_info, func, sinfo)
        def LogRecord_getMessageNewStyleFormatting():
            self = record
            msg = str(self.msg)
            args = self.args
            if args:
                if not isinstance(args, tuple):
                    args = (args,)
                msg = msg.format(*args)
            return msg
        record.getMessage = LogRecord_getMessageNewStyleFormatting
        return record
    log.makeRecord = Logger_makeRecordWrapper
    return log

def registerLogging(root_logger_name):
    global root_logger, root_logger_formatter, root_logger_stream_handler, root_logger_file_handler, root_logger_operator_report_handler
    root_logger = logging.getLogger(root_logger_name)
    root_logger_stream_handler = logging.StreamHandler()
    root_logger_file_handler = None
    root_logger_operator_report_handler = None
    root_logger_formatter = logging.Formatter('{levelname:s}:{name:s}.{funcName:s}: {message:s}', style='{')
    root_logger_stream_handler.setFormatter(root_logger_formatter)
    root_logger.addHandler(root_logger_stream_handler)
    root_logger.setLevel(1) # actual level filtering is left to handlers
    resetLoggingSettings()
    getLogger('logging_util').debug('Logging OK')

def setConsoleLevel(level):
    global root_logger_stream_handler
    root_logger_stream_handler.setLevel(level)

def setConsoleLevelDefault(level):
    global default_level_console
    default_level_console = level
    setConsoleLevel(level)

def setLogFile(path):
    global root_logger, root_logger_formatter, root_logger_file_handler
    if root_logger_file_handler:
        root_logger.removeHandler(root_logger_file_handler)
        root_logger_file_handler = None
    if path:
        root_logger_file_handler = logging.FileHandler(path, mode='w')
        root_logger_file_handler.setFormatter(root_logger_formatter)
        root_logger.addHandler(root_logger_file_handler)
        root_logger_file_handler.setLevel(1)

class OperatorReportLogHandler(logging.Handler):
    def __init__(self, operator):
        super().__init__()
        self.operator = operator

    def flush(self):
        pass

    def emit(self, record):
        try:
            type = 'DEBUG'
            for levelType,  minLevel in (
                ('ERROR',   logging.WARNING),
                ('WARNING', logging.INFO),
                ('INFO',    logging.DEBUG)
            ):
                if record.levelno > minLevel:
                    type = levelType
                    break
            msg = self.format(record)
            self.operator.report({type}, msg)
        except Exception:
            self.handleError(record)

def setLogOperator(operator, level=logging.INFO):
    global root_logger, root_logger_formatter, root_logger_operator_report_handler
    if root_logger_operator_report_handler:
        root_logger.removeHandler(root_logger_operator_report_handler)
        root_logger_operator_report_handler = None
    if operator:
        root_logger_operator_report_handler = OperatorReportLogHandler(operator)
        root_logger_operator_report_handler.setFormatter(root_logger_formatter)
        root_logger_operator_report_handler.setLevel(level)
        root_logger.addHandler(root_logger_operator_report_handler)

def resetLoggingSettings():
    setConsoleLevel(default_level_console)
    setLogFile(None)
    setLogOperator(None)

def unregisterLogging():
    global root_logger, root_logger_stream_handler
    resetLoggingSettings()
    root_logger.removeHandler(root_logger_stream_handler)

debug_levels_str = 'trace={:d} debug={:d} info={:d}'.format(logging_trace_level, logging.DEBUG, logging.INFO)
default_level_console = logging.INFO
default_level_report = logging.INFO
minimum_level = 1
maximum_level = 51
