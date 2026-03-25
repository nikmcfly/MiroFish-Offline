"""
Configuration management
Loads config from project root .env file
"""

import os
from dotenv import load_dotenv

# Load .env from project root
# Path: MiroFish/.env (relative to backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # Fall back to environment variables (for production)
    load_dotenv(override=True)


class Config:
    """Flask configuration"""

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    # JSON — disable ASCII escaping so CJK characters display directly
    JSON_AS_ASCII = False

    # LLM (unified OpenAI format)
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'http://localhost:11434/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'qwen2.5:32b')

    # Neo4j graph database
    NEO4J_URI = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.environ.get('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD', 'mirofish')

    # Embedding
    EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL', 'nomic-embed-text')
    EMBEDDING_BASE_URL = os.environ.get('EMBEDDING_BASE_URL', 'http://localhost:11434')

    # File upload
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}

    # Text processing
    DEFAULT_CHUNK_SIZE = 500
    DEFAULT_CHUNK_OVERLAP = 50

    # OASIS simulation
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')

    # OASIS platform actions
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]

    # Report Agent
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))

    # Prediction Market
    POLYMARKET_GAMMA_URL = os.environ.get('POLYMARKET_GAMMA_URL', 'https://gamma-api.polymarket.com')
    PREDICTION_DEFAULT_AGENTS = int(os.environ.get('PREDICTION_DEFAULT_AGENTS', '50'))
    PREDICTION_DEFAULT_ROUNDS = int(os.environ.get('PREDICTION_DEFAULT_ROUNDS', '2'))
    PREDICTION_SIGNAL_THRESHOLD = float(os.environ.get('PREDICTION_SIGNAL_THRESHOLD', '0.10'))
    PREDICTION_TRADE_ENABLED = os.environ.get('PREDICTION_TRADE_ENABLED', 'false').lower() == 'true'
    PREDICTION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/predictions')

    # Simulation LLM override — OASIS/camel-ai needs OpenAI-compatible API
    SIMULATION_LLM_API_KEY = os.environ.get('SIMULATION_LLM_API_KEY', '')
    SIMULATION_LLM_BASE_URL = os.environ.get('SIMULATION_LLM_BASE_URL', '')
    SIMULATION_LLM_MODEL = os.environ.get('SIMULATION_LLM_MODEL', '')

    # Signal calibration parameters
    CALIBRATION_MARKET_REGRESSION = float(os.environ.get('CALIBRATION_MARKET_REGRESSION', '0.30'))
    CALIBRATION_DATE_DAMPENING_DAYS = int(os.environ.get('CALIBRATION_DATE_DAMPENING_DAYS', '14'))
    CALIBRATION_HIGH_EDGE_THRESHOLD = float(os.environ.get('CALIBRATION_HIGH_EDGE_THRESHOLD', '0.25'))
    CALIBRATION_HIGH_EDGE_MAX_REDUCTION = float(os.environ.get('CALIBRATION_HIGH_EDGE_MAX_REDUCTION', '0.40'))
    CALIBRATION_SHORT_DATE_PENALTY = float(os.environ.get('CALIBRATION_SHORT_DATE_PENALTY', '0.20'))

    # SQLite storage
    SQLITE_DB_PATH = os.environ.get(
        'SQLITE_DB_PATH',
        os.path.join(os.path.dirname(__file__), '../data/mirofish.db')
    )

    # Paper trading
    PAPER_TRADING_MODE = os.environ.get('PAPER_TRADING_MODE', 'true').lower() == 'true'

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY not configured (set to any non-empty value, e.g. 'ollama')")
        if not cls.NEO4J_URI:
            errors.append("NEO4J_URI not configured")
        if not cls.NEO4J_PASSWORD:
            errors.append("NEO4J_PASSWORD not configured")
        return errors
