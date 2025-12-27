"""
NilüferAKS API Blueprints
"""
from flask import Blueprint

# Blueprint tanımlamaları
vehicles_bp = Blueprint('vehicles', __name__, url_prefix='/api')
neighborhoods_bp = Blueprint('neighborhoods', __name__, url_prefix='/api')
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api')
routes_bp = Blueprint('routes', __name__, url_prefix='/api')
gamification_bp = Blueprint('gamification', __name__, url_prefix='/api/gamification')

# API modüllerini import et
from . import vehicles, neighborhoods, dashboard, routes_api, gamification
