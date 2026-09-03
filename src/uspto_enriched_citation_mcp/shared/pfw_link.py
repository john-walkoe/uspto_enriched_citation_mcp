"""The PFW hand-off sentence, in one place.

It used to exist twice: `tools/_shared.PFW_LINK_HINT` for the envelope and an
inline f-string in `services/oa_citation_service` for the per-row custom-field
path. Both are contract strings pinned by tests and by eval `tr-hp-07`, so a
wording change in one silently split the contract in two (D-9).

It lives in `shared/` rather than `tools/` because a service importing from
`tools/` would invert the layering (L-3); both sides import down to here.
"""

#: `{app}` is substituted with an application number, or left as the
#: `<patentApplicationNumber>` placeholder on the envelope form.
PFW_LINK_TEMPLATE = "Use PFW MCP: PFW_get_application_documents(app_number={app})"

#: Envelope form: one line covering a result set spanning any number of
#: applications, so the sentence is stated once instead of once per row.
PFW_LINK_HINT = PFW_LINK_TEMPLATE.format(app="<patentApplicationNumber>")


def pfw_link_for(app_number: str) -> str:
    """Per-row form, for the custom-field path that pins the inline shape."""
    return PFW_LINK_TEMPLATE.format(app=f"'{app_number}'")
