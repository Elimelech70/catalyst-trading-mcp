# services/shared/market_schedule.py

import pytz
from datetime import datetime, time
from typing import Dict, Tuple, bool

class MarketSchedule:
    """Market hours and trading schedule management"""

    def __init__(self):
        self.eastern = pytz.timezone('US/Eastern')

        # Market hours (all times in EST)
        self.schedule = {
            'pre_market': {
                'start': time(4, 0),   # 4:00 AM
                'end': time(9, 30),    # 9:30 AM
                'trading_mode': 'aggressive',
                'scan_frequency': 300,  # 5 minutes
                'enabled': True
            },
            'market_hours': {
                'start': time(9, 30),  # 9:30 AM
                'end': time(16, 0),    # 4:00 PM
                'trading_mode': 'normal',
                'scan_frequency': 900,  # 15 minutes
                'enabled': True
            },
            'after_hours': {
                'start': time(16, 0),  # 4:00 PM
                'end': time(20, 0),    # 8:00 PM
                'trading_mode': 'conservative',
                'scan_frequency': 1800,  # 30 minutes
                'enabled': True
            }
        }

    def get_current_market_session(self) -> Tuple[str, Dict]:
        """Get current market session"""
        now = datetime.now(self.eastern)
        current_time = now.time()
        current_day = now.weekday()  # 0=Monday, 6=Sunday

        # Check if it's a weekday
        if current_day >= 5:  # Weekend
            return 'closed', {'reason': 'weekend'}

        # Check each session
        for session_name, config in self.schedule.items():
            if config['start'] <= current_time < config['end']:
                return session_name, config

        return 'closed', {'reason': 'outside_hours'}

    def is_market_open(self) -> bool:
        """Check if market is currently open"""
        session, _ = self.get_current_market_session()
        return session != 'closed'

    def get_trading_config(self) -> Dict:
        """Get current trading configuration"""
        session, config = self.get_current_market_session()

        if session == 'closed':
            return {
                'trading_enabled': False,
                'scan_frequency': 3600,  # 1 hour
                'mode': 'monitoring'
            }

        return {
            'trading_enabled': config.get('enabled', False),
            'scan_frequency': config.get('scan_frequency', 900),
            'mode': config.get('trading_mode', 'normal')
        }