"""
API route modules
"""

from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
simulation_bp = Blueprint('simulation', __name__)
report_bp = Blueprint('report', __name__)
prediction_bp = Blueprint('prediction', __name__)
backtest_bp = Blueprint('backtest', __name__)

from . import graph  # noqa: E402, F401
from . import simulation  # noqa: E402, F401
from . import report  # noqa: E402, F401
from . import prediction  # noqa: E402, F401
from . import backtest  # noqa: E402, F401
