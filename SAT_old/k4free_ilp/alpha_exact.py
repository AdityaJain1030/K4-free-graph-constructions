"""Re-export shim — canonical implementation lives in utils/graph_props.py."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils.graph_props import alpha_exact  # noqa: F401
