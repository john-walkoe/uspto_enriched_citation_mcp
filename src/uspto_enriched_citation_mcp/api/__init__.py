"""
API client for USPTO Enriched Citation API v3.
"""

import asyncio
import json
import structlog
from typing import Any, Dict, Optional

import aiohttp
from pydantic import BaseModel

from ..config.settings import Settings

logger = structlog.get_logger(__name__)


class CitationResponse(BaseModel):
    """Response model for citation searches."""

    text: str
    count: int
    start: int
    rows: int
    request_id: str = Optional[None]


class EnrichedCitationClient:
    """Client for USPTO Enriched Citation API v3."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.base_url
        self.api_key = settings.uspto_ecitation_api_key
        self.timeout = aiohttp.ClientTimeout(total=settings.citation_timeout)

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "USPTO-Enriched-Citation-MCP/0.1.0",
        }

    async def _make_request(
        self, endpoint: str, method: str = "GET", data: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Make HTTP request to USPTO API."""
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()

        request_id = "".join([str(ord(c) % 10) for c in str(id(endpoint))])[:8]

        async with aiohttp.ClientSession(
            headers=headers, timeout=self.timeout
        ) as session:
            try:
                logger.info(
                    "Making API request",
                    endpoint=endpoint,
                    method=method,
                    request_id=request_id,
                )

                if method.upper() == "POST" and data:
                    async with session.post(url, json=data) as response:
                        if response.status == 200:
                            result = await response.json()
                            logger.info(
                                "API request successful",
                                endpoint=endpoint,
                                request_id=request_id,
                                status=response.status,
                            )
                            return result
                        else:
                            error_text = await response.text()
                            logger.error(
                                "API request failed",
                                endpoint=endpoint,
                                status=response.status,
                                error=error_text,
                                request_id=request_id,
                            )
                            return None

                else:  # GET request
                    async with session.get(url) as response:
                        if response.status == 200:
                            result = await response.json()
                            logger.info(
                                "API request successful",
                                endpoint=endpoint,
                                request_id=request_id,
                                status=response.status,
                            )
                            return result
                        else:
                            error_text = await response.text()
                            logger.error(
                                "API request failed",
                                endpoint=endpoint,
                                status=response.status,
                                error=error_text,
                                request_id=request_id,
                            )
                            return None

            except asyncio.TimeoutError:
                logger.error(
                    "API request timed out",
                    endpoint=endpoint,
                    timeout=self.timeout.total,
                    request_id=request_id,
                )
                return None
            except Exception as e:
                logger.error(
                    "API request exception",
                    endpoint=endpoint,
                    error=str(e),
                    request_id=request_id,
                )
                return None

    async def get_available_fields(self, field_category: str = "all") -> Dict[str, Any]:
        """Get list of available fields from the API."""
        logger.info("Getting available fields", category=field_category)

        result = await self._make_request(
            "/enriched_cited_reference_metadata/v3/fields"
        )

        if not result:
            return {"text": "Failed to retrieve available fields"}

        try:
            fields = result.get("fields", [])
            if field_category != "all":
                # Simple field filtering by category (basic implementation)
                category_map = {
                    "identifiers": [
                        "citedReferenceIdentifier",
                        "applicationNumberText",
                        "patentNumber",
                    ],
                    "decision": [
                        "decisionTypeCodeDescriptionText",
                        "decisionDate",
                        "citingOfficeMailDate",
                    ],
                    "classification": [
                        "uspcClassification",
                        "cpcClassificationBag",
                        "technologyCenter",
                    ],
                    "cross_reference": [
                        "groupArtUnitNumber",
                        "examinerNameText",
                        "firstApplicantName",
                    ],
                }
                fields = [
                    f for f in fields if f in category_map.get(field_category, [])
                ]

            formatted_fields = "\n".join(
                f"- {field}" for field in fields[:50]
            )  # Limit display

            response_text = f"""
# Available Fields ({len(fields)} total)

{formatted_fields}

## Field Categories

**Core Identifiers:**
- `citedReferenceIdentifier`: Unique citation identifier (UUID)
- `applicationNumberText`: Patent application number (cross-reference to PFW MCP)  
- `patentNumber`: Patent number if granted (cross-reference to PTAB MCP)

**Decision Information:**
- `decisionTypeCodeDescriptionText`: CITED/DISCARDED/REFERRED/FOLLOWED
- `decisionDate`: Date of citation decision
- `citingOfficeMailDate`: Date of office action containing citation

**Classification:**
- `groupArtUnitNumber`: Art unit number (analysis across MCPs)
- `technologyCenter`: Technology center (1600-3700)
- `uspcClassification`: US Patent Classification
- `cpcClassificationBag`: CPC classification array

**Entity & Context:**
- `firstApplicantName`: Primary applicant/party name
- `examinerNameText`: Primary examiner name
- `inventionTitle`: Patent or application title

## Usage Examples

```sql
applicationNumberText:16751234
decisionTypeCode:CITED AND technologyCenter:2100
firstApplicantName:"Apple Inc"
groupArtUnitNumber:2854 AND decisionTypeCode:CITED
```

{f"*Showing {len(fields[:50])} of {len(fields)} fields. Use balanced searches for complete field access*" if len(fields) > 50 else ""}
"""

            return {"text": response_text}

        except Exception as e:
            logger.error("Failed to process available fields", error=str(e))
            return {"text": f"Error processing available fields: {str(e)}"}

    async def validate_query(self, query: str) -> Dict[str, Any]:
        """Validate Lucene query and provide optimization suggestions."""
        logger.info("Validating query", query=query[:100])  # Log truncated query

        # Basic query validation
        issues = []
        suggestions = []

        # Check for common issues
        if not query.strip():
            issues.append("Query is empty")

        # Check for balanced quotes
        quote_count = query.count('"')
        if quote_count % 2 != 0:
            issues.append("Unbalanced quotes in query")
            suggestions.append("Ensure all quoted phrases have closing quotes")

        # Check for field syntax
        field_indicators = query.count(":")
        if field_indicators > 0:
            # Check for invalid field patterns
            if ":*" in query:
                suggestions.append(
                    "Use prefix wildcards (:*) sparingly as they can be slow"
                )

            # Check for date range syntax
            if "[" in query and "TO" in query and "]" in query:
                suggestions.append(
                    "Date range syntax looks correct. Consider using compact format."
                )

            # Check parentheses balance
            paren_count = query.count("(") - query.count(")")
            if paren_count != 0:
                issues.append("Unbalanced parentheses")
                suggestions.append("Ensure all '(' have matching ')'")

        # Generate optimized version suggestions
        if "AND" not in query and " " in query:
            suggestions.append(
                "Consider using AND for multiple terms instead of implicit AND"
            )

        if "OR" not in query:
            suggestions.append(
                "Consider using OR for broader searches when appropriate"
            )

        response_text = f"""
# Query Validation Results

**Original Query:**
```sql
{query}
```

**Validation Status:** {"✅ Valid" if not issues else "❌ Issues Found"}
"""

        if issues:
            issues_str = "\n".join(f"- {issue}" for issue in issues)
            response_text += f"""
## Issues Found
{issues_str}
"""

        if suggestions:
            suggestions_str = "\n".join(suggestions)
            response_text += f"""
## Optimization Suggestions
{suggestions_str}
"""

        response_text += """
## Enhanced Query Examples

**Field-Specific Search:**
```sql
applicationNumberText:16751234
firstApplicantName:"Apple Inc"  
technologyCenter:2100 AND decisionTypeCode:CITED
groupArtUnitNumber:2854 AND citingOfficeMailDate:[2023-01-01 TO 2023-12-31]
```

**Advanced Techniques:**
```sql
# Complex boolean logic
(decisionTypeCode:CITED OR decisionTypeCode:FOLLOWED) AND technologyCenter:2100

# Pattern matching  
firstApplicantName:*Tech* AND inventionTitle:machine*

# Proximity search
inventionTitle:"wireless charging"~10

# Multi-field search
applicationNumberText:16751234 AND examinerNameText:Smith*
```

**Performance Tips:**
- Use field-specific searches for better performance
- Balance result size vs. information needs
- Consider date ranges for temporal analysis
- Validate syntax before large batch queries
"""

        try:
            # Try to run the query with limit=1 to test syntax
            test_result = await self.search_citations(
                criteria=query, start=0, rows=1, field_set="minimal"
            )
            if test_result and test_result.get("count", 0) > 0:
                response_text += "\n\n**✅ Query Syntax Verified:** Your Lucene syntax appears valid and returned results."

        except Exception:
            response_text += "\n\n**⚠️ Syntax Warning:** Could not validate query syntax. Check field names and operators."

        return {"text": response_text}

    async def search_citations(
        self, criteria: str, start: int = 0, rows: int = 50, field_set: str = "minimal"
    ) -> Optional[CitationResponse]:
        """Search citations using Lucene query syntax."""
        logger.info(
            "Searching citations",
            criteria=criteria[:100] if criteria else "empty",
            start=start,
            rows=rows,
            field_set=field_set,
        )

        # In real implementation, field_set would select predefined fields from YAML
        # For now, return a mock response structure

        request_data = {"criteria": criteria, "start": start, "rows": rows}

        result = await self._make_request(
            "/enriched_cited_reference_metadata/v3/records",
            method="POST",
            data=request_data,
        )

        if not result:
            return None

        try:
            response = CitationResponse(
                text=json.dumps(result, indent=2),
                count=result.get("count", 0),
                start=start,
                rows=rows,
                request_id="demo-id",
            )

            logger.info(
                "Search completed successfully",
                count=response.count,
                field_set=field_set,
            )

            return response

        except Exception as e:
            logger.error("Failed to process search response", error=str(e))
            return None

    async def get_citation_details(
        self, citation_id: str, include_context: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific citation."""
        logger.info(
            "Getting citation details",
            citation_id=citation_id,
            include_context=include_context,
        )

        # In real implementation, this would fetch the specific citation record
        # For now, return a mock detailed response

        demo_details = {
            "citedReferenceIdentifier": citation_id,
            "applicationNumberText": "16751234",
            "patentNumber": "10,234,567",
            "firstApplicantName": "Technology Company Inc",
            "decisionTypeCodeDescriptionText": "CITED",
            "decisionDate": "2023-05-15",
            "citingOfficeMailDate": "2023-04-20",
            "inventionTitle": "Advanced Machine Learning System for Patent Classification",
            "examinerNameText": "Smith, John A.",
            "groupArtUnitNumber": "2854",
            "technologyCenter": "2100",
            "applicationFilingDate": "2021-03-12",
            "uspcClassification": "706/30",
            "cpcClassificationBag": ["G06F 16/50", "G06N 20/00", "G06K 9/62"],
            "patentStatusCodeDescriptionText": "Patent Granted",
            "patentGrantDate": "2023-07-18",
            "finalDecidingOfficeName": "USPTO Technology Center 2100",
        }

        if include_context:
            demo_details.update(
                {
                    "citingContext": {
                        "officeActionType": "Non-Final Office Action",
                        "citingApplication": "17654321",
                        "citingExaminer": "Johnson, Mary K.",
                        "contextPassage": "The examiner finds that the claimed invention is anticipated by Smith et al. in US Patent 10,123,456, which teaches a similar machine learning architecture for patent classification. Accordingly, the claims are rejected under 35 U.S.C. § 102.",
                        "relevanceScore": 0.95,
                    }
                }
            )

        response_text = f"""
# Citation Details

## Core Information
- **Citation ID:** {demo_details["citedReferenceIdentifier"]}
- **Application Number:** {demo_details["applicationNumberText"]}
- **Patent Number:** {demo_details["patentNumber"]}
- **Applicant:** {demo_details["firstApplicantName"]}

## Decision Information
- **Decision Type:** {demo_details["decisionTypeCodeDescriptionText"]}
- **Decision Date:** {demo_details["decisionDate"]}
- **Citing Action Date:** {demo_details["citingOfficeMailDate"]}
- **Deciding Office:** {demo_details["finalDecidingOfficeName"]}

## Technical Information
- **Invention Title:** {demo_details["inventionTitle"]}
- **Art Unit:** {demo_details["groupArtUnitNumber"]}
- **Technology Center:** {demo_details["technologyCenter"]}
- **USPC Classification:** {demo_details["uspcClassification"]}
- **CPC Classifications:** {", ".join(demo_details["cpcClassificationBag"])}
- **Filing Date:** {demo_details["applicationFilingDate"]}

## Status Information
- **Application Status:** {demo_details["patentStatusCodeDescriptionText"]}
- **Grant Date:** {demo_details["patentGrantDate"]}

"""
        citing_context_section = ""
        if include_context:
            citing_app = demo_details.get("citingContext", {}).get(
                "citingApplication", "N/A"
            )
            citing_examiner = demo_details.get("citingContext", {}).get(
                "citingExaminer", "N/A"
            )
            office_action_type = demo_details.get("citingContext", {}).get(
                "officeActionType", "N/A"
            )
            context_passage = demo_details.get("citingContext", {}).get(
                "contextPassage", "N/A"
            )
            relevance_score = demo_details.get("citingContext", {}).get(
                "relevanceScore", "N/A"
            )

            citing_context_section = f"""
## Citing Context
- **Citing Application:** {citing_app}
- **Citing Examiner:** {citing_examiner}
- **Office Action Type:** {office_action_type}

- **Context Passage:**
{context_passage}

- **Relevance Score:** {relevance_score}
"""

        response_text += citing_context_section

        return {"text": response_text}
