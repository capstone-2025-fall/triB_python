import json
import numpy as np
from decimal import Decimal


class NumpyJSONEncoder(json.JSONEncoder):
    """NumPy 타입을 Python 네이티브 타입으로 변환하는 커스텀 JSONEncoder"""

    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def numpy_safe_dumps(obj, **kwargs):
    """NumPy 안전 JSON 직렬화 함수"""
    kwargs.setdefault('cls', NumpyJSONEncoder)
    kwargs.setdefault('ensure_ascii', False)
    return json.dumps(obj, **kwargs)
