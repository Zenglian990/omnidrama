"""OmniDrama 电影级 AI 短剧自动化生成引擎."""
import sys
from pathlib import Path

_BASE = Path(__file__).parent.resolve()
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))
