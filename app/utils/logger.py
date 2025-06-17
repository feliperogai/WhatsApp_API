logger_py = ""
import logging
import sys
from loguru import logger as loguru_logger
from app.config.settings import settings

class InterceptHandler(logging.Handler):
    
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        loguru_logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

def setup_logger():
    
    # Remove handler padrão do loguru
    loguru_logger.remove()
    
    # Configura formatação
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    # Handler para console
    loguru_logger.add(
        sys.stdout,
        format=log_format,
        level="DEBUG" if settings.debug else "INFO",
        colorize=True
    )
    
    # Handler para arquivo
    loguru_logger.add(
        "logs/jarvis_whatsapp_{time:YYYY-MM-DD}.log",
        format=log_format,
        level="INFO",
        rotation="1 day",
        retention="30 days",
        compression="zip"
    )
    
    # Intercepta logs do Python padrão
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    # Configura níveis para bibliotecas específicas
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    
    loguru_logger.info("Logging system initialized") 
