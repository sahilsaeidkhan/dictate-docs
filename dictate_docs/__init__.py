"""dictate-docs: turn dictated developer notes into polished docs.

A voice-first dev tool built for the Wispr "No Hands" Challenge (Builders track).
The default engine is a rule/heuristic-based offline text processor -- no network,
no API keys. An optional pluggable LLM backend can be enabled via environment
variables (see dictate_docs.llm).
"""

__version__ = "0.1.0"
__author__ = "Sahil Saeid"

from . import engine, commit, readme_gen, llm, pipeline  # noqa: F401
