"""L4: prompt-injection defence, toxicity screen, output filter. Rule-based baseline: extend with a classifier model."""
import re

INJECTION = [r"ignore (all |any )?(the )?(previous|prior|above) (instructions|prompts?)", r"disregard (the )?(system|previous)",
             r"you are now", r"system prompt", r"reveal (your|the) (prompt|instructions)", r"\bjailbreak\b",
             r"act as (an? )?(admin|root|customs officer)", r"approve this", r"<\s*/?\s*(system|assistant|untrusted)\s*>",
             r"override (the )?(rules|policy|classification)", r"file (the|a) (declaration|bill of entry)"]
TOXIC = [r"\b(idiot|stupid|moron|shut up)\b", r"\b(kill|murder) (you|them)\b"]
FORBIDDEN_OUTPUT = [r"declaration (has been |was )?(filed|submitted)", r"\bapproved for (export|filing)\b",
                    r"i (have )?(filed|submitted)", r"licen[cs]e (has been )?(granted|issued)", r"cleared by customs"]


def scan_text(text):
    t = text.lower()
    for p in INJECTION:
        if re.search(p, t):
            return "prompt_injection"
    for p in TOXIC:
        if re.search(p, t):
            return "toxicity"
    return None


def scan_request(req):
    """Every free-text field that can reach a model."""
    fields = [req.get("product_description", "")] + list(req.get("materials") or [])
    for f in fields:
        c = scan_text(f)
        if c:
            return c
    return None


def wrap_untrusted(text):
    return "<untrusted>\n" + text.replace("<", "&lt;") + "\n</untrusted>"


def filter_output(text):
    """The system may only *propose*. Strip any language that reads as a determination or filing."""
    out = text
    for p in FORBIDDEN_OUTPUT:
        out = re.sub(p, "[removed: not an authorised determination]", out, flags=re.I)
    if scan_text(out) == "toxicity":
        out = "[removed: toxic content]"
    return out
