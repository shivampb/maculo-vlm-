"""Condition presets and the prompt templates used for zero-shot matching."""

TEMPLATES = (
    "This is a skin image of {}",
    "A photo of skin with {}",
    "A clinical photograph showing {}",
)

LABEL_GROUPS: dict[str, list[str]] = {
    "Acne and follicles": [
        "acne",
        "pimple",
        "cystic acne",
        "folliculitis",
        "rosacea",
        "perioral dermatitis",
        "hidradenitis suppurativa",
    ],
    "Inflammatory": [
        "eczema",
        "atopic dermatitis",
        "contact dermatitis",
        "seborrheic dermatitis",
        "psoriasis",
        "lichen planus",
        "hives",
        "pityriasis rosea",
        "lupus",
    ],
    "Infections": [
        "ringworm",
        "tinea",
        "fungal infection",
        "tinea versicolor",
        "candidiasis",
        "impetigo",
        "cellulitis",
        "scabies",
        "herpes simplex",
        "shingles",
        "chickenpox",
        "molluscum contagiosum",
        "warts",
    ],
    "Pigment": [
        "vitiligo",
        "melasma",
        "post-inflammatory hyperpigmentation",
        "freckles",
        "café-au-lait spot",
    ],
    "Growths": [
        "nevus",
        "seborrheic keratosis",
        "skin tag",
        "cherry angioma",
        "lipoma",
        "dermatofibroma",
        "cyst",
        "keloid",
    ],
    "Pre-cancer and cancer": [
        "actinic keratosis",
        "basal cell carcinoma",
        "squamous cell carcinoma",
        "melanoma",
    ],
    "Other": [
        "keratosis pilaris",
        "stretch marks",
        "sunburn",
        "insect bite",
        "bruise",
        "burn",
        "scar",
        "healthy skin",
    ],
}

# The starting selection in the web app: common conditions plus a healthy baseline.
DEFAULT_SELECTION = [
    "acne",
    "pimple",
    "rosacea",
    "eczema",
    "psoriasis",
    "fungal infection",
    "ringworm",
    "warts",
    "hives",
    "hidradenitis suppurativa",
    "melanoma",
    "nevus",
    "healthy skin",
]

ALL_LABELS = [label for group in LABEL_GROUPS.values() for label in group]
