"""Provider-agnostic LLM access.

The LLM is used in exactly one place on the critical path (Query Understanding) and
optionally for explanation phrasing. Keeping it behind one interface lets providers
(Groq / Gemini / Ollama) be swapped without touching agent logic.
"""
