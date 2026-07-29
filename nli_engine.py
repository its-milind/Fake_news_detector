import os
import json
from pathlib import Path
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from groq import Groq
from tavily import TavilyClient
from huggingface_hub import InferenceClient

# 1. Environment variable setup
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)




# --- Data Transfer Models (Pydantic v2) ---

class ClaimExtractionResult(BaseModel):
    atomic_claim: str = Field(description="The core atomic claim requiring verification")
    search_query: str = Field(description="Search engine query optimized to retrieve factual news regarding this claim")


class NLIEvaluation(BaseModel):
    snippet: str
    source_url: str
    entailment_prob: float
    neutral_prob: float
    contradiction_prob: float
    nli_label: str


class FinalReport(BaseModel):
    original_text: str
    extracted_claim: str
    verdict: str
    confidence_score: float
    summary_explanation: str
    evidence_breakdown: List[Dict[str, Any]]


# --- Main NLI Fact Checker Engine (Serverless Architecture) ---

class NLIFactCheckerEngine:
    def __init__(self, nli_model_name: str = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"):
        groq_key = os.getenv("GROQ_API_KEY")
        tavily_key = os.getenv("TAVILY_API_KEY")
        hf_token = os.getenv("HF_TOKEN")

        if not groq_key or not tavily_key or not hf_token:
            raise ValueError(
                "Environment variables GROQ_API_KEY, TAVILY_API_KEY, and HF_TOKEN must be set in your .env file."
            )

        self.groq_client = Groq(api_key=groq_key)
        self.tavily_client = TavilyClient(api_key=tavily_key)
        
        # Serverless Hugging Face Client
        self.nli_model_name = nli_model_name
        self.hf_client = InferenceClient(token=hf_token)
        print(f"[NLI Engine] Connected to HF Serverless API for model: {self.nli_model_name}")

    def extract_claim_and_query(self, text: str) -> ClaimExtractionResult:
        prompt = f"""
        Extract the core factual claim from the text below and construct a search query to verify it.
        Text: "{text}"
        Return JSON with keys: "atomic_claim" and "search_query".
        """
        response = self.groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        data = json.loads(response.choices[0].message.content)
        return ClaimExtractionResult(**data)

    def fetch_web_evidence(self, query: str) -> List[Dict[str, str]]:
        search_res = self.tavily_client.search(query=query, search_depth="advanced", max_results=4)
        evidence = []
        for res in search_res.get("results", []):
            evidence.append({
                "url": res.get("url", ""),
                "content": res.get("content", "")
            })
        return evidence

    def run_nli_inference(self, claim: str, evidence_list: List[Dict[str, str]]) -> List[NLIEvaluation]:
        evaluations = []
        
        for item in evidence_list:
            premise = item["content"]
            hypothesis = claim

            # HF Zero-Shot Classification using DeBERTa
            # Maps premise against hypothesis candidate labels
            try:
                response = self.hf_client.zero_shot_classification(
                    text=premise,
                    candidate_labels=[hypothesis, f"Not {hypothesis}"],
                    hypothesis_template="This text implies {}",
                    model=self.nli_model_name
                )
                
                # Derive entailment vs contradiction/neutral from top scores
                top_score = round(float(response[0]["score"]), 4) if response else 0.0
                top_label = response[0]["label"] if response else ""

                if top_label == hypothesis:
                    entail_p = top_score
                    contra_p = round(1.0 - top_score, 4)
                    neutral_p = 0.0
                    nli_label = "ENTAILMENT"
                else:
                    contra_p = top_score
                    entail_p = round(1.0 - top_score, 4)
                    neutral_p = 0.0
                    nli_label = "CONTRADICTION"

            except Exception as e:
                print(f"[NLI Engine Warning] HF API Inference failed for snippet: {e}")
                # Fallback to default neutral probabilities on API timeout/error
                entail_p, neutral_p, contra_p = 0.33, 0.34, 0.33
                nli_label = "NEUTRAL"

            evaluations.append(NLIEvaluation(
                snippet=premise[:250] + "...",
                source_url=item["url"],
                entailment_prob=entail_p,
                neutral_prob=neutral_p,
                contradiction_prob=contra_p,
                nli_label=nli_label
            ))
            
        return evaluations

    def synthesize_final_report(self, original_text: str, claim: str, evals: List[NLIEvaluation]) -> FinalReport:
        # Pydantic v2 compatibility: model_dump()
        evals_dict = [e.model_dump() for e in evals]
        
        prompt = f"""
        You are an expert Fact-Checker. Evaluate the authenticity of the claim using the evidence below.

        ORIGINAL TEXT: "{original_text}"
        EXTRACTED CLAIM: "{claim}"
        EVIDENCE: {json.dumps(evals_dict, indent=2)}

        INSTRUCTIONS:
        1. Set verdict to one of: ['VERIFIED_REAL', 'FALSE', 'UNVERIFIED', 'CONTRADICTORY'].
        2. Assign a confidence score from 0.0 to 1.0.
        3. Provide a concise 3-sentence summary explanation stating whether live sources contradict or verify the claim. Avoid mentioning internal technology 
        details like 'probability scores' or 'NLI' Also if the claim is contradictory or false, then give correct information.

        Return JSON with keys: "verdict", "confidence_score", "summary_explanation".
        """
        response = self.groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        data = json.loads(response.choices[0].message.content)
        return FinalReport(
            original_text=original_text,
            extracted_claim=claim,
            verdict=data["verdict"],
            confidence_score=data["confidence_score"],
            summary_explanation=data["summary_explanation"],
            evidence_breakdown=evals_dict
        )

    def analyze(self, article_text: str) -> FinalReport:
        claim_obj = self.extract_claim_and_query(article_text)
        evidence = self.fetch_web_evidence(claim_obj.search_query)

        # Fallback handling for empty web evidence
        if not evidence:
            return FinalReport(
                original_text=article_text,
                extracted_claim=claim_obj.atomic_claim,
                verdict="UNVERIFIED",
                confidence_score=0.0,
                summary_explanation="No web evidence could be retrieved to verify or refute this claim.",
                evidence_breakdown=[]
            )

        evals = self.run_nli_inference(claim_obj.atomic_claim, evidence)
        report = self.synthesize_final_report(article_text, claim_obj.atomic_claim, evals)
        return report


# --- Standalone Test Execution ---
if __name__ == "__main__":
    print("Initializing NLI Fact Checker Engine...")
    engine = NLIFactCheckerEngine()

    sample_input = "NASA announced they discovered liquid water oceans on Mars yesterday."
    print(f"\nAnalyzing Sample Claim: '{sample_input}'...")

    report = engine.analyze(sample_input)

    print("\n================ FINAL REPORT ================")
    print(f"Extracted Claim : {report.extracted_claim}")
    print(f"Verdict         : {report.verdict}")
    print(f"Confidence      : {report.confidence_score}")
    print(f"Explanation     : {report.summary_explanation}")