# -*- coding: utf-8 -*-
"""路由蓝图注册。"""
from .main import bp as main_bp
from .auth import bp as auth_bp
from .chat import bp as chat_bp
from .reader import bp as reader_bp
from .manager import bp as manager_bp
from .realtime import bp as realtime_bp
from .companion import bp as companion_bp

from .voiceprint import bp as voiceprint_bp
from .cat_agent import bp as cat_agent_bp

from .portals import bp as portals_bp

from .cat_market import bp as cat_market_bp

from .supplies import bp as supplies_bp
from .pet_studio import bp as pet_studio_bp
from .farm import bp as farm_bp
from .pet_voice import bp as pet_voice_bp
from .mobile import bp as mobile_bp

from .pet_care import bp as pet_care_bp
from .native import bp as native_bp

ALL_BLUEPRINTS = (native_bp, pet_care_bp, mobile_bp, pet_voice_bp, farm_bp, pet_studio_bp, supplies_bp, cat_market_bp, portals_bp, cat_agent_bp, voiceprint_bp, main_bp, auth_bp, chat_bp, reader_bp, manager_bp, realtime_bp, companion_bp)
