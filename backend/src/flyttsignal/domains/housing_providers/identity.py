PROVIDER_NAME_ALIASES = {
    "balder": "balder",
    "fastighets ab balder": "balder",
    "heimstaden": "heimstaden",
    "hsb": "hsb-uppsala",
    "hsb uppsala": "hsb-uppsala",
    "ikano bostad": "ikano-bostad",
    "ikano bostad ab": "ikano-bostad",
    "juli living": "juli-living",
    "klövern": "klovern",
    "lansa": "lansa",
    "lansa fastigheter": "lansa",
    "newsec": "newsec",
    "riksbyggen": "riksbyggen",
    "rikshem": "rikshem",
    "stena fastigheter": "stena-fastigheter",
    "sveaviken pm": "sveaviken-pm",
    "uppsalahem": "uppsalahem",
    "victoriahem": "victoriahem",
}


def canonical_provider_key(name: str, fallback_namespace: str, external_id: object) -> str:
    normalized_name = " ".join(name.casefold().split())
    known = PROVIDER_NAME_ALIASES.get(normalized_name)
    if known:
        return known
    try:
        return f"{fallback_namespace}-{int(str(external_id))}"
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{fallback_namespace} provider has no stable identity") from exc
