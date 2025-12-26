from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from enum import Enum

# -------------------------------------------------
# Handle imports from both API and worker contexts
# -------------------------------------------------

from apps.worker.pipeline.config import (
    InvoiceStatus,
    OLLAMA_MODEL,
    DEFAULT_CURRENCY,
)

LLM_MODEL_NAME = OLLAMA_MODEL  
LLM_TEMPERATURE = 0.1
ENABLE_LLM = True

PDF_EXTS = {".pdf"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}

# ============================================
# UAE-SPECIFIC CONFIGURATION
# ============================================

# All UAE expense categories
UAE_CATEGORIES = [
    "Occupancy & Facilities",
    "Telecom & Connectivity", 
    "Travel & Transport",
    "IT, Software & Cloud",
    "Professional, Banking & Insurance",
    "Office Supplies",
    "Marketing & Advertising",
    "Other Business Expenses"
]

DEFAULT_CATEGORY = "Other Business Expenses"


# Vendor name normalization 
UAE_VENDOR_NORMALIZATION = {
    # Utilities
    "dewa": "DEWA",
    "dubai electricity": "DEWA",
    "dubai water": "DEWA",
    "dubai electricity and water": "DEWA",
    "dubai electricity & water authority": "DEWA",
    
    # Telecom
    "etisalat": "Etisalat",
    "e&": "Etisalat",
    "emirates telecommunications": "Etisalat",
    "du": "du",
    "emirates integrated telecommunications": "du",
    "virgin mobile": "Virgin Mobile",
    
    # Fuel
    "enoc": "ENOC",
    "emirates national oil company": "ENOC",
    "eppco": "EPPCO",
    "adnoc": "ADNOC",
    "abu dhabi national oil company": "ADNOC",
    "emarat": "Emarat",
    
    # Government & RTA
    "rta": "RTA",
    "roads and transport authority": "RTA",
    "roads & transport authority": "RTA",
    "salik": "Salik",
    "dubai land department": "Dubai Land Department",
    "dld": "Dubai Land Department",
    "ejari": "Ejari",
    "tawtheeq": "Tawtheeq",
    "amer": "AMER",
    "gdrfa": "GDRFA",
    "general directorate of residency": "GDRFA",
    "dubai municipality": "Dubai Municipality",
    "ded": "DED",
    "department of economic development": "DED",
    "mohre": "MOHRE",
    "ministry of human resources": "MOHRE",
    
    # Cloud providers
    "amazon web services": "AWS",
    "aws": "AWS",
    "microsoft azure": "Microsoft Azure",
    "azure": "Microsoft Azure",
    "google cloud": "Google Cloud",
    "gcp": "Google Cloud",
}


# Direct vendor-to-category mapping (highest priority)
VENDOR_TO_CATEGORY = {
    # Utilities
    "DEWA": "Occupancy & Facilities",
    
    # Telecom
    "Etisalat": "Telecom & Connectivity",
    "du": "Telecom & Connectivity",
    "Virgin Mobile": "Telecom & Connectivity",
    
    # Fuel
    "ENOC": "Travel & Transport",
    "EPPCO": "Travel & Transport",
    "ADNOC": "Travel & Transport",
    "Emarat": "Travel & Transport",
    
    # Government/RTA
    "RTA": "Travel & Transport",
    "Salik": "Travel & Transport",
    "Dubai Land Department": "Occupancy & Facilities",
    "Ejari": "Occupancy & Facilities",
    "Tawtheeq": "Occupancy & Facilities",
    "AMER": "Professional, Banking & Insurance",
    "GDRFA": "Professional, Banking & Insurance",
    "Dubai Municipality": "Professional, Banking & Insurance",
    "DED": "Professional, Banking & Insurance",
    "MOHRE": "Professional, Banking & Insurance",
    
    # Cloud
    "AWS": "IT, Software & Cloud",
    "Microsoft Azure": "IT, Software & Cloud",
    "Google Cloud": "IT, Software & Cloud",
}


# Category detection keywords - if these appear in the invoice text, suggest the category
# Format: category -> list of keywords to look for
CATEGORY_KEYWORDS = {
    "Occupancy & Facilities": [
        "dewa", "electricity", "water bill", "utility bill",
        "office rent", "rental", "lease agreement", "tenancy",
        "ejari", "tawtheeq", "dld", "dubai land department",
        "chiller", "district cooling", "empower", "tabreed",
        "building maintenance", "facilities management", "fm contract",
        "cleaning services", "security services", "parking fees"
    ],
    
    "Telecom & Connectivity": [
        "etisalat", "e&", "du", "virgin mobile",
        "mobile", "telecom", "internet", "broadband",
        "data plan", "phone bill", "sim card", "roaming",
        "landline", "voip", "fiber", "wifi"
    ],
    
    "Travel & Transport": [
        "fuel", "petrol", "diesel", "enoc", "eppco", "adnoc", "emarat",
        "salik", "toll", "parking", "rta",
        "vehicle registration", "registration renewal", "mulkiya",
        "traffic fine", "vehicle insurance", "car rental",
        "taxi", "uber", "careem", "metro", "bus",
        "flight", "airline", "hotel", "travel"
    ],
    
    "IT, Software & Cloud": [
        "aws", "amazon web services", "azure", "google cloud", "gcp",
        "software", "saas", "subscription", "license",
        "domain", "hosting", "server", "cloud storage",
        "microsoft 365", "office 365", "google workspace",
        "adobe", "zoom", "slack", "dropbox", "github",
        "antivirus", "cybersecurity", "ssl", "api"
    ],
    
    "Professional, Banking & Insurance": [
        "trade license", "license renewal", "business license",
        "visa", "emirates id", "medical fitness", "immigration",
        "work permit", "labour card", "establishment card",
        "pro services", "public relations officer",
        "accounting", "audit", "bookkeeping", "tax consultancy",
        "legal", "lawyer", "attorney", "law firm",
        "insurance", "health insurance", "medical insurance",
        "business insurance", "liability insurance",
        "bank charges", "bank fees", "swift", "transfer fee"
    ],
    
    "Office Supplies": [
        "stationery", "office supplies", "printer", "cartridge",
        "paper", "pens", "folders", "files",
        "desk", "chair", "furniture", "equipment",
        "pantry", "coffee", "water dispenser"
    ],
    
    "Marketing & Advertising": [
        "marketing", "advertising", "ads", "campaign",
        "social media", "facebook ads", "google ads", "instagram",
        "seo", "sem", "digital marketing", "content creation",
        "branding", "design", "graphics", "print",
        "billboard", "signage", "banner", "flyer"
    ]
}


# Transaction type keywords
OPERATIONAL_EXPENSE_KEYWORDS = [
    "dewa", "etisalat", "du", "virgin mobile",
    "rent", "ejari", "utility", "telecom",
    "visa", "emirates id", "medical fitness",
    "insurance", "government fee", "municipality"
]


# -------------------------------------------------
# Vendor normalization and category detection
# -------------------------------------------------

def normalize_vendor_name(raw_vendor: str) -> str:
    """
    Clean up and normalize vendor names using UAE mappings.
    
    Examples:
        "DUBAI ELECTRICITY AND WATER AUTHORITY" -> "DEWA"
        "etisalat by e&" -> "Etisalat"
        "Abu Dhabi National Oil Company" -> "ADNOC"
    """
    if not raw_vendor:
        return "Unknown Vendor"
    
    vendor_lower = raw_vendor.lower().strip()
    
    # Check against normalization map
    for pattern, normalized in UAE_VENDOR_NORMALIZATION.items():
        if pattern in vendor_lower:
            return normalized
    
    # Remove common suffixes
    vendor_clean = raw_vendor.strip()
    for suffix in [" LLC", " L.L.C", " FZ-LLC", " FZE", " FZCO", " PJSC", " EST"]:
        if vendor_clean.upper().endswith(suffix):
            vendor_clean = vendor_clean[:-len(suffix)].strip()
    
    return vendor_clean


def detect_category_from_text(text: str, vendor: Optional[str] = None) -> Optional[str]:
    """
    Use rule-based keyword matching to detect category before LLM.
    This gives the LLM a strong hint and improves accuracy.
    
    Returns category name or None if can't determine.
    """
    # First priority: check vendor directly
    if vendor:
        normalized_vendor = normalize_vendor_name(vendor)
        if normalized_vendor in VENDOR_TO_CATEGORY:
            return VENDOR_TO_CATEGORY[normalized_vendor]
    
    # Second priority: keyword matching in text
    text_lower = text.lower()
    
    # Count keyword matches for each category
    category_scores: Dict[str, int] = {cat: 0 for cat in UAE_CATEGORIES}
    
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                category_scores[category] += 1
    
    # Get category with most matches
    max_score = max(category_scores.values())
    if max_score >= 2:  # Need at least 2 keyword matches to be confident
        for category, score in category_scores.items():
            if score == max_score:
                return category
    
    return None


def detect_transaction_type(text: str, vendor: Optional[str] = None) -> str:
    """
    Determine if this is a B2B invoice or operational expense.
    
    Returns: "operational_expense" or "b2b"
    """
    text_lower = text.lower()
    vendor_lower = (vendor or "").lower()
    
    # Check for operational expense keywords
    for keyword in OPERATIONAL_EXPENSE_KEYWORDS:
        if keyword in text_lower or keyword in vendor_lower:
            return "operational_expense"
    
    # Default to B2B for supplier invoices
    return "b2b"


# -------------------------------------------------
# OCR helpers
# -------------------------------------------------

try:
    import pdfplumber  # type: ignore
except ImportError:  # pragma: no cover
    pdfplumber = None  # type: ignore

try:
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore
except ImportError:  # pragma: no cover
    pytesseract = None  # type: ignore
    Image = None  # type: ignore

try:
    import ollama  # type: ignore
except ImportError:  # pragma: no cover
    ollama = None  # type: ignore


def _extract_pdf_text(path: Path) -> str:
    if pdfplumber is None:
        return ""

    text_chunks = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            try:
                txt = page.extract_text() or ""
            except Exception:
                txt = ""
            text_chunks.append(txt)

    text = "\n".join(text_chunks).strip()
    return text


def _extract_image_text(path: Path) -> str:
    if pytesseract is None or Image is None:
        return ""
    
    # Use both English and Arabic for UAE documents
    img = Image.open(str(path))
    try:
        # Try with Arabic + English
        text = pytesseract.image_to_string(img, lang='eng+ara')
    except:
        # Fallback to English only
        text = pytesseract.image_to_string(img, lang='eng')
    
    return text


def extract_text_with_ocr_if_needed(path: Path) -> Tuple[str, str]:
    """
    Extract text from PDF or image, falling back to OCR when needed.

    Returns (text, source_label) where source_label is one of:
        'pdf_text', 'ocr_image', 'ocr_pdf', 'ocr_only'
    """
    suffix = path.suffix.lower()

    if suffix in PDF_EXTS:
        # Try extracting text directly from PDF first
        text = _extract_pdf_text(path)
        if text and len(text.strip()) > 50:  # Has meaningful text
            return text, "pdf_text"

        # Convert PDF to images and OCR them
        print(f"[OCR] PDF has no extractable text, performing OCR...")
        
        if pytesseract is None or Image is None:
            print("[OCR] WARNING: pytesseract/PIL not available, cannot OCR PDF")
            return text or "", "ocr_pdf"
        
        try:
            # Use pdf2image to convert PDF to images
            try:
                from pdf2image import convert_from_path
            except ImportError:
                print("[OCR] WARNING: pdf2image not installed, cannot OCR PDF")
                print("[OCR] Install with: pip install pdf2image")
                return text or "", "ocr_pdf"
            
            # Convert PDF pages to images
            images = convert_from_path(str(path))
            
            # OCR each page
            ocr_texts = []
            for i, img in enumerate(images):
                print(f"[OCR] Processing page {i+1}/{len(images)}...")
                try:
                    # Try Arabic + English for UAE documents
                    page_text = pytesseract.image_to_string(img, lang='eng+ara')
                except:
                    # Fallback to English only
                    page_text = pytesseract.image_to_string(img, lang='eng')
                
                ocr_texts.append(page_text)
            
            ocr_text = "\n\n".join(ocr_texts).strip()
            print(f"[OCR] Extracted {len(ocr_text)} characters from {len(images)} page(s)")
            
            return ocr_text, "ocr_pdf"
            
        except Exception as e:
            print(f"[OCR] ERROR during PDF OCR: {e}")
            import traceback
            traceback.print_exc()
            return text or "", "ocr_pdf"

    if suffix in IMAGE_EXTS:
        text = _extract_image_text(path)
        return text, "ocr_image"

    # Unknown extension, attempt OCR image fallback
    text = _extract_image_text(path)
    return text, "ocr_only"


# -------------------------------------------------
# LLM extraction
# -------------------------------------------------

@dataclass
class InvoiceExtraction:
    vendor: Optional[str] = None
    date: Optional[str] = None  # ISO format YYYY-MM-DD
    amount: Optional[float] = None
    currency: Optional[str] = None
    tax_amount: Optional[float] = None
    category: Optional[str] = None
    payment_method: Optional[str] = None

    # Distinguishes normal vendor invoices vs operational expenses
    transaction_type: Optional[str] = None  # "b2b" or "operational_expense"

    is_paid: Optional[bool] = None

    ocr_confidence: Optional[float] = None
    extraction_confidence: Optional[float] = None
    status: InvoiceStatus = InvoiceStatus.NEEDS_REVIEW

    review_reason: Optional[str] = None
    review_questions: List[dict] = field(default_factory=list)


# -------------------------------------------------
# Review questions builder
# -------------------------------------------------

def build_review_questions(result: InvoiceExtraction) -> Tuple[List[dict], str]:
    """
    Generate targeted clarification questions based on what's missing or uncertain.
    Returns (questions, reason) where reason explains why review is needed.
    
    Max 4 questions to keep it manageable.
    """
    questions = []
    reasons = []

    # Missing amount is critical
    if result.amount is None:
        questions.append({
            "field_name": "amount",
            "question": "What is the total amount on this invoice?",
            "input_type": "number",
            "current_value": None,
            "hint": "Enter the final total including VAT (in AED unless stated otherwise)"
        })
        reasons.append("amount missing")

    # Missing date
    if result.date is None:
        questions.append({
            "field_name": "date",
            "question": "What is the invoice date?",
            "input_type": "date",
            "current_value": None,
            "hint": "Format: DD/MM/YYYY (e.g., 15/03/2024)"
        })
        reasons.append("date missing")

    # Missing or empty vendor
    if not result.vendor or result.vendor.strip() == "":
        questions.append({
            "field_name": "vendor",
            "question": "Who is the vendor or supplier?",
            "input_type": "text",
            "current_value": result.vendor,
            "hint": "Company name as shown on the invoice"
        })
        reasons.append("vendor missing")

    # Payment status unknown - important for cash flow tracking
    if result.is_paid is None:
        questions.append({
            "field_name": "is_paid",
            "question": "Has this invoice been paid?",
            "input_type": "select",
            "current_value": None,
            "options": [
                {"value": True, "label": "Yes, paid"},
                {"value": False, "label": "No, still outstanding"},
                {"value": None, "label": "Not sure"}
            ]
        })
        reasons.append("payment status unclear")

    # Category missing
    if result.category is None:
        questions.append({
            "field_name": "category",
            "question": "What category does this expense belong to?",
            "input_type": "select",
            "current_value": None,
            "options": [
                {"value": "Occupancy & Facilities", "label": "Occupancy & Facilities (rent, DEWA, Ejari)"},
                {"value": "Telecom & Connectivity", "label": "Telecom & Connectivity (Etisalat, du)"},
                {"value": "Travel & Transport", "label": "Travel & Transport (Salik, RTA, fuel)"},
                {"value": "IT, Software & Cloud", "label": "IT, Software & Cloud (AWS, subscriptions)"},
                {"value": "Professional, Banking & Insurance", "label": "Professional & Banking (licenses, insurance, PRO)"},
                {"value": "Office Supplies", "label": "Office Supplies"},
                {"value": "Marketing & Advertising", "label": "Marketing & Advertising"},
                {"value": "Other Business Expenses", "label": "Other Business Expenses"}
            ]
        })
        reasons.append("category missing")

    # Low confidence even if fields are present
    conf = result.extraction_confidence or 0.0
    if conf < 0.5 and len(questions) == 0:
        # Ask user to verify the key fields
        questions.append({
            "field_name": "amount",
            "question": f"Please verify: is the total amount AED {result.amount:.2f}?",
            "input_type": "confirm_or_correct",
            "current_value": result.amount,
            "hint": "Confirm if correct, or enter the right amount"
        })
        reasons.append("low extraction confidence")

    # Cap at 4 questions max
    questions = questions[:4]
    
    # Build reason string
    if reasons:
        reason = "Needs review: " + ", ".join(reasons[:3])
        if len(reasons) > 3:
            reason += f" (+{len(reasons) - 3} more)"
    else:
        reason = "Needs manual verification"

    return questions, reason


def _determine_status(result: InvoiceExtraction) -> Tuple[InvoiceStatus, str]:
    """
    Decide if extraction is OK or needs review.
    Returns (status, reason).
    """
    issues = []
    
    # Critical fields check
    if result.amount is None:
        issues.append("no amount")
    if result.date is None:
        issues.append("no date")
    if not result.vendor:
        issues.append("no vendor")
    
    # Confidence check
    conf = result.extraction_confidence or 0.0
    if conf < 0.6:
        issues.append(f"low confidence ({conf:.0%})")
    
    # If we have critical issues, needs review
    if issues:
        return InvoiceStatus.NEEDS_REVIEW, ", ".join(issues)
    
    # High confidence and all fields present = OK
    if conf >= 0.75:
        return InvoiceStatus.OK, ""
    
    # Medium confidence - still needs review but less urgent
    return InvoiceStatus.NEEDS_REVIEW, f"medium confidence ({conf:.0%})"


# Enhanced LLM prompt with detailed UAE examples
LLM_EXTRACTION_SYSTEM_PROMPT = """You are an expert invoice parser specialized in UAE (United Arab Emirates) business documents.

Your task: Extract structured data from invoice/receipt text with HIGH ACCURACY for UAE-specific vendors and expense types.

========================================
EXPENSE CATEGORIES (Choose ONE)
========================================

1. "Occupancy & Facilities"
   WHEN TO USE: Rent, utilities, building services
   EXAMPLES:
   - DEWA electricity/water bills
   - Office rent payments
   - Ejari registration fees
   - Tawtheeq rental contracts
   - DLD (Dubai Land Department) payments
   - Chiller/cooling charges (Empower, Tabreed)
   - Building maintenance, cleaning, security services
   - Parking fees at office building
   KEYWORDS: DEWA, electricity, water, rent, lease, Ejari, DLD, chiller, facilities

2. "Telecom & Connectivity"
   WHEN TO USE: Phone, internet, mobile services
   EXAMPLES:
   - Etisalat (e&) mobile/internet bills
   - du telecom services
   - Virgin Mobile
   - Business internet/broadband
   - Landline services
   - Data plans, SIM cards
   KEYWORDS: Etisalat, e&, du, Virgin Mobile, telecom, internet, mobile, broadband

3. "Travel & Transport"
   WHEN TO USE: Fuel, tolls, vehicle-related, travel expenses
   EXAMPLES:
   - Fuel receipts (ENOC, EPPCO, ADNOC, Emarat)
   - Salik toll charges
   - RTA vehicle registration/renewal
   - RTA traffic fines
   - Parking fees
   - Taxi/Uber/Careem
   - Flight tickets, hotel bookings
   - Car rental
   KEYWORDS: fuel, ENOC, EPPCO, ADNOC, Salik, RTA, vehicle, parking, taxi, flight

4. "IT, Software & Cloud"
   WHEN TO USE: Cloud services, software subscriptions, tech services
   EXAMPLES:
   - AWS (Amazon Web Services)
   - Microsoft Azure
   - Google Cloud (GCP)
   - Office 365 / Microsoft 365
   - Google Workspace
   - Adobe Creative Cloud
   - Zoom, Slack, Dropbox subscriptions
   - Domain registrations, web hosting
   - Antivirus software
   KEYWORDS: AWS, Azure, Google Cloud, software, SaaS, subscription, cloud, hosting, domain

5. "Professional, Banking & Insurance"
   WHEN TO USE: Business licenses, visas, legal, accounting, insurance, banking
   EXAMPLES:
   - Trade license renewals (DED)
   - Visa processing fees (GDRFA, AMER)
   - Emirates ID issuance/renewal
   - Medical fitness tests for visas
   - PRO (Public Relations Officer) services
   - Accounting/audit services
   - Legal consultancy
   - Health/medical insurance
   - Business insurance policies
   - Bank charges, transfer fees
   KEYWORDS: license, visa, Emirates ID, PRO, accounting, legal, insurance, bank fees

6. "Office Supplies"
   WHEN TO USE: Stationery, office equipment, furniture
   EXAMPLES:
   - Stationery (pens, paper, folders)
   - Printer cartridges
   - Office furniture (desks, chairs)
   - Pantry supplies (coffee, water)
   KEYWORDS: stationery, printer, paper, furniture, pantry

7. "Marketing & Advertising"
   WHEN TO USE: Marketing campaigns, ads, design, branding
   EXAMPLES:
   - Facebook/Instagram ads
   - Google Ads campaigns
   - SEO/SEM services
   - Graphic design work
   - Billboard/signage
   - Social media management
   KEYWORDS: marketing, advertising, ads, campaign, social media, design, SEO

8. "Other Business Expenses"
   WHEN TO USE: Anything that doesn't fit above categories
   EXAMPLES:
   - Miscellaneous business expenses
   - One-off purchases
   - Unusual services
   DEFAULT: Use this if truly uncertain

========================================
CATEGORY SELECTION LOGIC
========================================

STEP 1 - Check vendor first:
- If vendor is DEWA → "Occupancy & Facilities"
- If vendor is Etisalat/du/Virgin Mobile → "Telecom & Connectivity"
- If vendor is ENOC/EPPCO/ADNOC/Emarat → "Travel & Transport"
- If vendor is AWS/Azure/Google Cloud → "IT, Software & Cloud"
- If vendor is RTA or Salik → "Travel & Transport"

STEP 2 - Check document type/keywords:
- Contains "electricity" or "water bill" → "Occupancy & Facilities"
- Contains "mobile" or "internet bill" → "Telecom & Connectivity"
- Contains "fuel" or "petrol" → "Travel & Transport"
- Contains "visa" or "Emirates ID" or "license renewal" → "Professional, Banking & Insurance"
- Contains "cloud" or "subscription" or "SaaS" → "IT, Software & Cloud"

STEP 3 - If still uncertain:
- Use "Other Business Expenses"

========================================
TRANSACTION TYPE
========================================

"operational_expense" = Regular business operating costs
USE FOR:
- DEWA, utilities
- Etisalat, du, Virgin Mobile (telecom)
- Office rent, Ejari fees
- Visas, Emirates ID, medical fitness
- Government fees (RTA, DED, Municipality)
- Insurance payments

"b2b" = Business-to-business vendor invoices
USE FOR:
- Supplier invoices
- Professional services (consultants, agencies)
- Software/SaaS vendors (AWS, Adobe, etc.)
- Most other invoices from companies

========================================
UAE-SPECIFIC DETAILS
========================================

Currency: Almost always AED unless explicitly stated otherwise (USD, EUR, etc.)

VAT: UAE standard rate is 5%
- Look for: "VAT", "VAT Amount", "TRN" (Tax Registration Number)
- If you see "5%" near "VAT" or "Tax", that's the VAT amount
- Some invoices are VAT-exempt (government fees, etc.)

Dates: Common formats in UAE:
- DD/MM/YYYY (e.g., 25/12/2024)
- DD-MM-YYYY
- "Invoice Date", "Bill Date", "Issue Date"
ALWAYS output as: YYYY-MM-DD

Vendor names often include:
- LLC, L.L.C, FZ-LLC, FZE, FZCO, PJSC, EST
- Remove these suffixes for cleaner vendor names

Payment detection:
- "Paid" / "Payment Received" → is_paid = true
- "Amount Due" / "Outstanding" → is_paid = false
- If unclear → is_paid = null

========================================
OUTPUT REQUIREMENTS
========================================

Return ONLY valid JSON (no markdown, no explanations):

{
  "vendor": "string or null",
  "date": "YYYY-MM-DD or null",
  "amount": number or null,
  "currency": "AED" or other,
  "tax_amount": number or null,
  "category": "one of the 8 categories above",
  "payment_method": "card/bank_transfer/cash or null",
  "transaction_type": "b2b" or "operational_expense",
  "is_paid": true/false/null,
  "extraction_confidence": 0.0 to 1.0
}

CONFIDENCE SCORING:
- 0.9-1.0: All fields clear, recognized vendor, unambiguous
- 0.7-0.9: Most fields clear, minor uncertainties
- 0.5-0.7: Some fields unclear or missing
- 0.3-0.5: Multiple fields unclear, low quality OCR
- 0.0-0.3: Very poor quality, mostly guessing

Be CONSERVATIVE with confidence. Better to mark for review than give wrong data.
"""


def _call_ollama(prompt: str) -> str:
    if not ENABLE_LLM or ollama is None:
        # For offline dev, return an empty JSON scaffold
        return json.dumps(
            {
                "vendor": None,
                "date": None,
                "amount": None,
                "currency": None,
                "tax_amount": None,
                "category": None,
                "payment_method": None,
                "transaction_type": "b2b",
                "is_paid": None,
                "extraction_confidence": 0.0,
            }
        )

    resp = ollama.chat(
        model=LLM_MODEL_NAME,
        messages=[
            {"role": "system", "content": LLM_EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        options={"temperature": LLM_TEMPERATURE},
    )
    return resp["message"]["content"]  # type: ignore[index]


def extract_fields_with_llm(text: str) -> InvoiceExtraction:
    """
    Extract structured invoice data from raw text using LLM.
    Includes pre-processing with UAE-specific rules before LLM.
    Automatically generates review questions if extraction is uncertain.
    """
    # Pre-processing: Try to detect category using rules first
    rule_based_category = detect_category_from_text(text)
    
    # Build prompt with hint if we detected category
    if rule_based_category:
        prompt = f"""Raw invoice text:

{text}

HINT: Based on keywords, this might be category "{rule_based_category}". Verify and confirm or correct.

Return JSON now."""
    else:
        prompt = f"Raw invoice text:\n\n{text}\n\nReturn JSON now."
    
    raw = _call_ollama(prompt)

    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            raw = raw[start : end + 1]

        data = json.loads(raw)
    except Exception:
        # Fallback: empty extraction
        data = {}

    def _as_float(v) -> Optional[float]:
        try:
            if v is None:
                return None
            return float(v)
        except Exception:
            return None

    vendor = data.get("vendor")
    
    # Normalize vendor name using our UAE mappings
    if vendor:
        vendor = normalize_vendor_name(vendor)
    
    date_raw = data.get("date")
    date_iso: Optional[str] = None
    if isinstance(date_raw, str) and date_raw.strip():
        # Try to normalize to YYYY-MM-DD
        try:
            dt = datetime.fromisoformat(date_raw.strip())
            date_iso = dt.strftime("%Y-%m-%d")
        except Exception:
            try:
                dt = datetime.strptime(date_raw.strip(), "%d/%m/%Y")
                date_iso = dt.strftime("%Y-%m-%d")
            except Exception:
                # Leave as raw string if we can't parse
                date_iso = date_raw.strip()

    category = data.get("category")
    if category and category not in UAE_CATEGORIES:
        # LLM returned invalid category, try to fix
        if rule_based_category:
            category = rule_based_category
        else:
            category = DEFAULT_CATEGORY
    elif not category and rule_based_category:
        # LLM didn't provide category, use rule-based
        category = rule_based_category
    
    # Detect transaction type using rules
    transaction_type = data.get("transaction_type")
    if not transaction_type or transaction_type not in ("b2b", "operational_expense"):
        transaction_type = detect_transaction_type(text, vendor)

    result = InvoiceExtraction(
        vendor=vendor,
        date=date_iso,
        amount=_as_float(data.get("amount")),
        currency=(data.get("currency") or "AED"),  # Default to AED for UAE
        tax_amount=_as_float(data.get("tax_amount")),
        category=category,
        payment_method=(data.get("payment_method") or None),
        transaction_type=transaction_type,
        is_paid=(
            bool(data.get("is_paid"))
            if isinstance(data.get("is_paid"), bool)
            else None
        ),
        ocr_confidence=None,
        extraction_confidence=_as_float(data.get("extraction_confidence")) or 0.0,
    )

    # Determine status and reason
    status, reason = _determine_status(result)
    result.status = status

    # Generate review questions if needed
    if status == InvoiceStatus.NEEDS_REVIEW:
        questions, review_reason = build_review_questions(result)
        result.review_questions = questions
        result.review_reason = review_reason
    else:
        result.review_questions = []
        result.review_reason = None

    return result


# -------------------------------------------------
# Review resolution (called from API layer)
# -------------------------------------------------

REVIEW_RESOLUTION_PROMPT = """You are helping fix an invoice that had extraction issues.

Original extracted data:
{original_data}

The user was asked these questions and provided answers:
{qa_pairs}

Your task:
- Update ONLY the fields that the user answered
- Do NOT change fields that weren't asked about
- Do NOT invent or guess values
- Return the complete updated invoice data as JSON

Return ONLY valid JSON with these keys:
- vendor, date, amount, currency, tax_amount, category, payment_method, transaction_type, is_paid
- extraction_confidence should be 0.9 (user-verified)
"""


def resolve_review_with_llm(
    original: InvoiceExtraction,
    questions: List[dict],
    answers: dict
) -> InvoiceExtraction:
    """
    Use LLM to update specific fields based on user answers.
    Only modifies fields that were explicitly answered.
    
    Args:
        original: The original extraction
        questions: The review questions that were asked
        answers: Dict mapping field_name -> user's answer
    
    Returns:
        Updated InvoiceExtraction with status=OK
    """
    # Build Q&A pairs for the prompt
    qa_pairs = []
    for q in questions:
        field = q["field_name"]
        if field in answers and answers[field] is not None:
            qa_pairs.append({
                "field": field,
                "question": q["question"],
                "answer": answers[field]
            })

    if not qa_pairs:
        # No answers provided, just return original
        return original

    original_data = {
        "vendor": original.vendor,
        "date": original.date,
        "amount": original.amount,
        "currency": original.currency,
        "tax_amount": original.tax_amount,
        "category": original.category,
        "payment_method": original.payment_method,
        "transaction_type": original.transaction_type,
        "is_paid": original.is_paid,
    }

    prompt = REVIEW_RESOLUTION_PROMPT.format(
        original_data=json.dumps(original_data, indent=2),
        qa_pairs=json.dumps(qa_pairs, indent=2)
    )

    if not ENABLE_LLM or ollama is None:
        # Offline mode: manually apply answers
        return _apply_answers_directly(original, answers)

    try:
        resp = ollama.chat(
            model=LLM_MODEL_NAME,
            messages=[
                {"role": "system", "content": "You update invoice data based on user corrections. Return only JSON."},
                {"role": "user", "content": prompt},
            ],
            options={"temperature": 0.0},  
        raw = resp["message"]["content"]
        )
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start:end + 1]
        
        data = json.loads(raw)
    except Exception:
        # Fallback: apply answers directly without LLM
        return _apply_answers_directly(original, answers)

    # Build updated extraction
    def _as_float(v) -> Optional[float]:
        try:
            return float(v) if v is not None else None
        except:
            return None

    updated = InvoiceExtraction(
        vendor=data.get("vendor", original.vendor),
        date=data.get("date", original.date),
        amount=_as_float(data.get("amount")) or original.amount,
        currency=data.get("currency", original.currency),
        tax_amount=_as_float(data.get("tax_amount")),
        category=data.get("category", original.category),
        payment_method=data.get("payment_method", original.payment_method),
        transaction_type=data.get("transaction_type", original.transaction_type),
        is_paid=data.get("is_paid") if isinstance(data.get("is_paid"), bool) else original.is_paid,
        ocr_confidence=original.ocr_confidence,
        extraction_confidence=0.9,  # User-verified = high confidence
        status=InvoiceStatus.OK,
        review_reason=None,
        review_questions=[],
    )
    
    return updated


def _apply_answers_directly(original: InvoiceExtraction, answers: dict) -> InvoiceExtraction:
    """
    Directly apply user answers without LLM.
    Used as fallback when LLM is disabled or fails.
    """
    updated = InvoiceExtraction(
        vendor=answers.get("vendor", original.vendor),
        date=answers.get("date", original.date),
        amount=float(answers["amount"]) if "amount" in answers and answers["amount"] else original.amount,
        currency=answers.get("currency", original.currency),
        tax_amount=float(answers["tax_amount"]) if "tax_amount" in answers and answers["tax_amount"] else original.tax_amount,
        category=answers.get("category", original.category),
        payment_method=answers.get("payment_method", original.payment_method),
        transaction_type=answers.get("transaction_type", original.transaction_type),
        is_paid=answers.get("is_paid") if "is_paid" in answers else original.is_paid,
        ocr_confidence=original.ocr_confidence,
        extraction_confidence=0.9,
        status=InvoiceStatus.OK,
        review_reason=None,
        review_questions=[],
    )
    return updated


# -------------------------------------------------
# Email invoice classification helper
# -------------------------------------------------

EMAIL_CLASSIFIER_SYSTEM_PROMPT = """You classify incoming emails as INVOICE or NOT_INVOICE.

Rules:
- If the email clearly contains or references an invoice, bill, receipt, statement of charges, pro forma invoice, or similar, answer exactly "INVOICE".
- Otherwise answer exactly "NOT_INVOICE".

Return only the single word: INVOICE or NOT_INVOICE.
"""


def classify_email_text(subject: str, body: str) -> str:
    """Return 'INVOICE' or 'NOT_INVOICE'."""
    text = f"Subject: {subject}\n\nBody:\n{body}"
    if not ENABLE_LLM or ollama is None:
        return "NOT_INVOICE"

    resp = ollama.chat(
        model=LLM_MODEL_NAME,
        messages=[
            {"role": "system", "content": EMAIL_CLASSIFIER_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        options={"temperature": 0.0},
    )
    answer = resp["message"]["content"].strip().upper()  # type: ignore[index]
    if "INVOICE" in answer and "NOT" not in answer:
        return "INVOICE"
    if answer.startswith("INVOICE"):
        return "INVOICE"
    return "NOT_INVOICE"