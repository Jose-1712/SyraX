"""
gemini_service.py
------------------
Server-side wrapper around the Gemini API (google-genai SDK).

SECURITY: the API key is read ONLY from the environment (GEMINI_API_KEY).
It is never hardcoded here and never sent to the browser. The frontend
calls our own Flask endpoint (/api/ai/insights); this module is the only
place that talks to Google.

Setup:
    pip install google-genai python-dotenv
    export GEMINI_API_KEY="your-key-here"     # or put it in a .env file
"""

import os

from google import genai

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("AQ.Ab8RN6IWWgiQyZSOwu4CvIBOzThQ0So7ng3RDF3MCFzkJwLVyg")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Set it as an environment variable "
                "(or Colab secret) before calling the AI insights endpoint."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def generate_insights(context: str, question: str = None, model: str = DEFAULT_MODEL) -> str:
    """
    context : plain-text summary of real data (demand forecast, battery
              health, cost savings, etc.) pulled from models/predict.py
              — Gemini reasons over YOUR numbers, it doesn't invent them.
    question: optional free-form question from the user; if omitted, a
              default "give me 3-5 actionable recommendations" prompt is used.
    """
    client = _get_client()

    prompt = f"""You are an energy-management assistant for an industrial plant.
Use ONLY the data below — do not invent numbers that aren't given.

DATA:
{context}

TASK:
{question or "Give 3-5 short, concrete, actionable recommendations "
             "(demand shifting, battery charge/discharge timing, "
             "maintenance/fault follow-up) based on this data. "
             "Use plain language, one recommendation per line, no preamble."}
"""

    response = client.models.generate_content(model=model, contents=prompt)
    return response.text.strip()


if __name__ == "__main__":
    sample_context = (
        "Latest actual demand: 612 kW. Peak forecast next 24h: 780 kW at 14:00.\n"
        "Battery: SoH 74%, RUL 7 cycles, fault_type=Aging, usable_capacity_fraction=0.52.\n"
        "Baseline cost: 11,064,925. RL-optimized cost: 10,989,169. Savings: 0.68%."
    )
    print(generate_insights(sample_context))
