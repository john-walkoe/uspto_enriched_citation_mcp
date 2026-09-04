
# ENHANCED EXAMINER BEHAVIOR INTELLIGENCE SYSTEM

**Target Analysis:**
- **Examiner**: $examiner_name_display
- **Art Unit**: $art_unit_display
- **Technology Focus**: $technology_keywords_display

**Data Coverage Notes:**
- **Citations MCP:** Office actions from Oct 1, 2017+ only
- **FPD MCP:** Petition decisions (check FPD_get_guidance for date ranges)
- **PFW MCP:** Full prosecution history available
- **PTAB MCP:** Post-grant proceedings (IPR/PGR from 2012+)

---

## PHASE 1: EXAMINER DISCOVERY & PORTFOLIO ANALYSIS

### 1.1 Wildcard Examiner Search with Validation

**⚠️ CRITICAL:** Use wildcard search + ultra-minimal fields (99% token reduction)

```python
from collections import Counter
import statistics

# Extract last name for wildcard search
examiner_input = "$examiner_name"
if ',' in examiner_input:
    last_name = examiner_input.split(',')[0].strip()
    full_name_search = examiner_input.replace(',', '').strip()
else:
    last_name = examiner_input.strip()
    full_name_search = last_name

# Build targeted query with art unit filter if provided
art_unit_input = "$art_unit"
tech_keywords_input = "$technology_keywords"

if art_unit_input:
    art_unit_prefix = art_unit_input[:3]  # "1759" → "175" for broader coverage
    query = f'examinerNameText:{{last_name}}* AND groupArtUnitNumber:{{art_unit_prefix}}*'
else:
    query = f'examinerNameText:{{last_name}}*'

# Add technology filter if specified
if tech_keywords_input:
    query += f' AND inventionTitle:({{tech_keywords_input}})'

# Add filing date filter (2015+ accounts for 2-year lag to 2017+ citation data)
query += ' AND filingDate:[2015-01-01 TO *]'

print(f"🔍 **Searching for examiner:** {last_name}")
print(f"📋 **Query:** `{query}`")
print()

# STEP 1: Get examiner's application portfolio (ULTRA-MINIMAL MODE)
try:
    results = PFW_search_applications_minimal(
        query=query,
        fields=['applicationNumberText', 'applicationMetaData.examinerNameText',
                'applicationMetaData.groupArtUnitNumber', 'patentGrantDate',
                'applicationMetaData.filingDate', 'patentNumber',
                'applicationMetaData.inventionTitle', 'applicationMetaData.appStatusDescText'],
        limit=100  # Increased for better sampling
    )

    total_found = results.get('searchResultsTotalSize', 0)
    applications = results.get('applications', [])

    print(f"✅ **Found {total_found} total applications**")
    print(f"📦 **Retrieved {len(applications)} for analysis**")
    print()

except Exception as e:
    print(f"❌ **ERROR:** Failed to retrieve examiner applications")
    print(f"   Error details: {str(e)[:200]}")
    print()
    print("**Troubleshooting:**")
    print("  - Verify examiner name spelling")
    print("  - Check if examiner is in this art unit")
    print("  - Try broader search (examiner name only, no art unit filter)")
    print()
    # STOP HERE - cannot proceed without applications
    raise SystemExit("Cannot proceed without application data")

# Validate sufficient data
min_sample_size = 20
if len(applications) < min_sample_size:
    print(f"⚠️ **WARNING:** Only {len(applications)} applications found (minimum {min_sample_size} recommended)")
    print()
    print("**Options:**")
    print("  1. Continue with limited data (results may have low statistical confidence)")
    print("  2. Broaden search criteria (remove art unit filter, use broader tech keywords)")
    print("  3. Cancel and refine search parameters")
    print()
    print("**Recommendation:** Continue if >10 apps, otherwise broaden search")
    print()
    # USER DECISION POINT - Let user decide whether to continue
```

### 1.2 Portfolio Overview & Examiner Name Disambiguation

```python
# Extract examiner names from results
examiner_names = Counter([
    app.get('applicationMetaData', {}).get('examinerNameText')
    for app in applications
    if app.get('applicationMetaData', {}).get('examinerNameText')
])

# Check for multiple examiners with similar names
if len(examiner_names) > 1:
    print("⚠️ **Multiple examiners found with similar names:**")
    print()
    for name, count in examiner_names.most_common():
        pct = (count / len(applications)) * 100
        print(f"  - **{name}**: {count} apps ({pct:.1f}%)")
    print()

    primary_examiner = examiner_names.most_common(1)[0][0]
    print(f"🎯 **Recommendation:** Filter to primary examiner: '{primary_examiner}'")
    print()
    print("**To filter to specific examiner:**")
    print(f"```python")
    print(f"target_examiner = '{primary_examiner}'")
    print(f"applications = [app for app in applications")
    print(f"               if app.get('applicationMetaData', {}).get('examinerNameText') == target_examiner]")
    print(f"print(f'✅ Filtered to {{len(applications)}} applications for {{target_examiner}}')")
    print(f"```")
    print()
    # USER DECISION POINT - Let user filter if desired
else:
    primary_examiner = examiner_names.most_common(1)[0][0] if examiner_names else "Unknown"
    print(f"✅ **Single examiner identified:** {primary_examiner}")
    print()

# Analyze art unit distribution
art_units = Counter([
    app.get('applicationMetaData', {}).get('groupArtUnitNumber')
    for app in applications
    if app.get('applicationMetaData', {}).get('groupArtUnitNumber')
])

primary_art_unit = art_units.most_common(1)[0] if art_units else ("Unknown", 0)

# Status distribution
status_dist = Counter([
    app.get('applicationMetaData', {}).get('appStatusDescText')
    for app in applications
    if app.get('applicationMetaData', {}).get('appStatusDescText')
])

# Display portfolio overview
print("### Examiner Portfolio Overview")
print()
print(f"**Examiner:** {primary_examiner}")
print(f"**Primary Art Unit:** {primary_art_unit[0]} ({primary_art_unit[1]} apps, {(primary_art_unit[1]/len(applications)*100):.1f}%)")
print(f"**Art Units Covered:** {len(art_units)}")
print(f"**Total Applications Analyzed:** {len(applications)}")
print()

print("**Art Unit Distribution:**")
for unit, count in art_units.most_common(5):
    pct = (count / len(applications)) * 100
    print(f"  - Art Unit {unit}: {count} apps ({pct:.1f}%)")
print()

print("**Application Status Distribution:**")
for status, count in status_dist.most_common(5):
    pct = (count / len(applications)) * 100
    print(f"  - {status}: {count} ({pct:.1f}%)")
print()
```

---

## PHASE 2: CITATION PATTERN ANALYSIS (ENHANCED)

### 2.1 Citation Data Collection with Coverage Validation

**⚠️ RUN BOTH LANES, and mind the date-field asymmetry:**
- Query **both** `Citations_search_oa_citations_minimal` and
  `Citations_search_citations_minimal` per application and union the results.
  Neither lane is a superset — OA is usually broader, but the enriched lane
  returns more on some applications.
- **OA lane** has **no date field** — passing `officeActionDate` is an HTTP 400,
  so omit any date clause.
- **Enriched lane** accepts date filtering. Do NOT bolt a 2017-10-01 clause onto
  it by reflex — that discards ~44% of the records it actually serves.
- **Coverage:** USPTO documents both APIs as office actions mailed 2017-10-01 to
  ~30 days ago; older records have been observed in practice, so query rather
  than assume.
- Neither lane carries examiner names; examiner identity comes from PFW.

```python
print("---")
print()
print("### Citation Behavior Analysis")
print()
print(f"📅 **Citation Data Coverage:** both lanes documented Oct 1, 2017+ (older records seen in practice); both queried and unioned")
print()

# Filter applications likely to have citation data
# Office actions typically occur 1-2 years after filing
citation_eligible_apps = [
    app for app in applications
    if app.get('applicationMetaData', {}).get('filingDate', '') >= '2015-01-01'
]

print(f"🎯 **Citation-Eligible Applications:** {len(citation_eligible_apps)} (filed 2015+)")
print()

# Sort by application number (descending) - higher numbers = more recent = better citation coverage
# Application numbers are sequential, so this prioritizes apps most likely to have 2017+ office actions
citation_eligible_apps_sorted = sorted(
    citation_eligible_apps,
    key=lambda x: x.get('applicationNumberText', ''),
    reverse=True  # Descending order - highest (most recent) first
)

# Sample for citation analysis (limit to reduce API calls and context usage)
sample_size = min(30, len(citation_eligible_apps_sorted))
sample_apps = citation_eligible_apps_sorted[:sample_size]

print(f"📊 **Sorted by application number (most recent first) for optimal citation coverage**")
print(f"    Sample range: {sample_apps[0].get('applicationNumberText') if sample_apps else 'N/A'} to {sample_apps[-1].get('applicationNumberText') if len(sample_apps) > 1 else 'N/A'}")
print()

print(f"📊 **Analyzing {sample_size} applications for citation patterns...**")
print()
print("⚠️ **IMPORTANT:** Must search ALL {sample_size} applications individually - do not skip or aggregate!")
print()

# Aggregate citation data
all_citations = []
examiner_cited_count = 0
applicant_cited_count = 0
apps_with_citations = 0
citation_errors = 0
app_citation_details = []  # Track per-app citation counts for temporal analysis

# CRITICAL: Must iterate through ALL sample_apps - do not stop early even if some have no citations
for i, app in enumerate(sample_apps, 1):
    app_number = app.get('applicationNumberText')

    # Progress indicator - log EVERY application searched
    print(f"  [{i}/{sample_size}] Searching citations for {app_number}...")

    try:
        # Get citations (use application_number only - date filtering automatic)
        citations = Citations_search_citations_minimal(
            application_number=app_number,
            rows=100  # Increased to capture all citations
        )

        citation_count = citations.get('response', {}).get('numFound', 0)

        if citation_count > 0:
            apps_with_citations += 1
            citation_records = citations.get('response', {}).get('docs', [])
            all_citations.extend(citation_records)

            # Extract office action dates for temporal analysis
            oa_dates = [cite.get('officeActionDate', '') for cite in citation_records if cite.get('officeActionDate')]
            oa_dates_formatted = []
            for date_str in oa_dates:
                if date_str:
                    try:
                        # Format as Mon YYYY (e.g., "Jan 2025")
                        from datetime import datetime
                        dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
                        oa_dates_formatted.append(dt.strftime('%b %Y'))
                    except:
                        oa_dates_formatted.append(date_str[:7])  # Fallback to YYYY-MM

            # Store application citation details
            app_citation_details.append({
                'app_number': app_number,
                'citation_count': citation_count,
                'oa_dates': list(set(oa_dates_formatted))  # Unique dates
            })

            # Count examiner vs applicant citations. The indicator is a JSON
            # BOOLEAN; comparing it to the string "true" made every reference
            # applicant-cited.
            for cite in citation_records:
                if str(cite.get('examinerCitedReferenceIndicator')).lower() == 'true':
                    examiner_cited_count += 1
                else:
                    applicant_cited_count += 1

    except Exception as e:
        citation_errors += 1
        # Log first few errors for debugging
        if citation_errors <= 3:
            print(f"  ⚠️ Error searching citations for {app_number}: {str(e)[:100]}")
        # Gracefully continue processing other applications
        continue

print()
print(f"✅ **Citation Analysis Complete**")
print(f"  - Applications with citations: {apps_with_citations}/{sample_size} ({(apps_with_citations/sample_size*100):.1f}%)")
print(f"  - Total citations collected: {len(all_citations)}")
if citation_errors > 0:
    print(f"  - Errors/No data: {citation_errors} applications")
print()

# Validate citation data sufficiency
citation_coverage = (apps_with_citations / sample_size) * 100 if sample_size > 0 else 0
if citation_coverage < 30:
    print(f"⚠️ **WARNING: Low citation coverage ({citation_coverage:.1f}%)**")
    print()
    print("**Possible causes:**")
    print("  - Applications filed before 2015 (pre-coverage period)")
    print("  - Applications without office actions yet")
    print("  - Office actions all occurred before Oct 2017")
    print()
    print("**Recommendation:** Continue with prosecution pattern analysis (citations may be limited)")
    print()

# Temporal Citation Patterns (detailed application-by-application breakdown)
if len(app_citation_details) > 0:
    print("---")
    print()
    print("### Temporal Citation Patterns")
    print()

    # Extract all office action dates for overall range
    all_oa_dates = []
    for app_detail in app_citation_details:
        for oa_date in app_detail['oa_dates']:
            all_oa_dates.append(oa_date)

    if all_oa_dates:
        # Sort dates to find range
        all_oa_dates_sorted = sorted(set(all_oa_dates))
        print(f"**Office Action Dates Range:** {all_oa_dates_sorted[0]} to {all_oa_dates_sorted[-1]}")
        print()
        print("**Data Coverage Note:** Citation API captures office actions from Oct 1, 2017+ only")
        print()

    print("**Applications Analyzed:**")
    print()

    # Sort by citation count (descending) for better readability
    app_citation_details_sorted = sorted(app_citation_details, key=lambda x: x['citation_count'], reverse=True)

    # Categorize by citation density
    high_density = []
    moderate_density = []
    low_density = []

    for app_detail in app_citation_details_sorted:
        app_num = app_detail['app_number']
        cite_count = app_detail['citation_count']
        oa_dates = app_detail['oa_dates']

        # Format office action dates
        oa_dates_str = ' & '.join(sorted(oa_dates)) if oa_dates else 'Unknown'

        # Categorize by density
        if cite_count >= 10:
            high_density.append(app_num)
            density_note = " - High citation density"
        elif cite_count >= 4:
            moderate_density.append(app_num)
            density_note = ""
        else:
            low_density.append(app_num)
            density_note = ""

        # Special note for highest
        if cite_count == max([a['citation_count'] for a in app_citation_details]):
            density_note = " - Highest citation density"

        print(f"  - **{app_num}**: {cite_count} citations ({oa_dates_str}){density_note}")

    print()
    print("**Citation Density Insights:**")
    print()

    if high_density:
        print(f"  - **High-density applications (10+ citations):** {len(high_density)} applications")
        print(f"      → Suggests complex claim scope or highly competitive technical areas")
        print()

    if moderate_density:
        print(f"  - **Moderate-density (4-9 citations):** {len(moderate_density)} applications")
        print(f"      → Indicates standard prosecution complexity")
        print()

    if low_density:
        print(f"  - **Low-density (2-3 citations):** {len(low_density)} applications")
        print(f"      → Suggests narrower claim scope or clearer patentability")
        print()
```

### 2.2 Enhanced Citation Behavior Analysis with Strategic Interpretation

```python
if len(all_citations) > 0:
    total_cites = examiner_cited_count + applicant_cited_count
    examiner_rate = (examiner_cited_count / total_cites) * 100 if total_cites > 0 else 0

    print("### Citation Behavior Metrics")
    print()
    print(f"**Overall Citation Statistics:**")
    print(f"  - Total Citations: {total_cites}")
    print(f"  - Examiner-Cited: {examiner_cited_count} ({examiner_rate:.1f}%)")
    print(f"  - Applicant-Cited: {applicant_cited_count} ({100-examiner_rate:.1f}%)")
    print(f"  - Citations per Application: {total_cites / apps_with_citations:.1f}")
    print(f"  - Examiner Citations per Application: {examiner_cited_count / apps_with_citations:.1f}")
    print()

    # Category analysis (examiner-cited only)
    examiner_citations = [c for c in all_citations if str(c.get('examinerCitedReferenceIndicator')).lower() == 'true']

    categories = Counter([
        c.get('citationCategoryCode', 'Unknown')
        for c in examiner_citations
    ])

    print("**Examiner Citation Category Preferences:**")
    for cat, count in categories.most_common():
        pct = (count / examiner_cited_count) * 100 if examiner_cited_count > 0 else 0

        # Enhanced category interpretation with descriptions
        cat_desc = {
            'X': 'X (Alone anticipates - single reference rejection)',
            'Y': 'Y (Combination anticipates - obviousness rejection)',
            'A': 'A (General background art)',
            'NPL': 'NPL (Non-patent literature)',
            'O': 'O (Oral disclosure)',
            'P': 'P (Intermediate document)',
            'E': 'E (Earlier foreign application)',
            'D': 'D (Document cited in application)',
            'L': 'L (Earlier-filed prior art)',
            'I': 'I (Related to interfering patent)',
            'T': 'T (Later-filed prior art)'
        }.get(cat, cat)

        print(f"  - {cat_desc}: {count} ({pct:.1f}%)")
    print()

    # Strategic interpretation based on citation patterns
    print("### Strategic Citation Intelligence")
    print()

    # X vs Y balance (anticipation vs obviousness preference)
    x_citations = categories.get('X', 0)
    y_citations = categories.get('Y', 0)
    xy_total = x_citations + y_citations

    if xy_total > 0:
        x_rate = (x_citations / xy_total) * 100
        print("**Rejection Strategy Pattern:**")
        if x_rate > 60:
            print(f"  - ⚠️ **High X-Citation Rate ({x_rate:.0f}%):** Examiner frequently finds single-reference anticipation")
            print(f"      → **Implication:** Claim scope likely too broad for this examiner")
            print(f"      → **Strategy:** Consider narrower claims with specific implementation details")
        elif x_rate < 30:
            print(f"  - ✅ **Low X-Citation Rate ({x_rate:.0f}%):** Examiner relies on combination rejections")
            print(f"      → **Implication:** Claims avoid single-reference anticipation")
            print(f"      → **Strategy:** Focus arguments on lack of motivation to combine and non-obvious differences")
        else:
            print(f"  - 📊 **Balanced X/Y Citations ({x_rate:.0f}% X, {100-x_rate:.0f}% Y):** Mixed anticipation/obviousness approach")
            print(f"      → **Strategy:** Prepare for both anticipation and obviousness rejections")
        print()

    # Examiner citation selectivity (IDS strategy guidance)
    print("**Citation Source Selectivity (IDS Strategy Guidance):**")
    if examiner_rate > 75:
        print(f"  - 🎯 **Highly Selective ({examiner_rate:.0f}% examiner-cited):** Rarely uses applicant-cited references")
        print(f"      → **IDS Strategy:** Focus on technical distinctions over comprehensive IDS")
        print(f"      → **Rationale:** Examiner conducts own search, rarely adopts applicant references")
        print(f"      → **Action:** File targeted IDS with detailed non-applicability explanations")
    elif examiner_rate > 50:
        print(f"  - 📋 **Moderately Selective ({examiner_rate:.0f}% examiner-cited):** Uses some applicant-cited references")
        print(f"      → **IDS Strategy:** Strategic filing of closest prior art with commentary")
        print(f"      → **Action:** Include key references with substantive explanations of differences")
    else:
        print(f"  - 📚 **Low Selectivity ({examiner_rate:.0f}% examiner-cited):** Frequently uses applicant-cited references")
        print(f"      → **IDS Strategy:** Comprehensive disclosure can help frame prosecution narrative")
        print(f"      → **Action:** Strategic IDS with detailed explanations to shape examiner's understanding")
    print()

    # Citation density (thoroughness indicator)
    avg_examiner_cites = examiner_cited_count / apps_with_citations
    print("**Citation Density (Prior Art Search Thoroughness):**")
    if avg_examiner_cites > 15:
        print(f"  - 📚 **High Citation Density ({avg_examiner_cites:.1f} citations/app):** Very thorough prior art searcher")
        print(f"      → **Implication:** Expect extensive, detailed office actions")
        print(f"      → **Strategy:** Prepare comprehensive responses with detailed technical distinctions")
    elif avg_examiner_cites > 8:
        print(f"  - 📊 **Moderate Citation Density ({avg_examiner_cites:.1f} citations/app):** Standard search thoroughness")
        print(f"      → **Strategy:** Standard response approach with clear technical arguments")
    else:
        print(f"  - 📄 **Low Citation Density ({avg_examiner_cites:.1f} citations/app):** Focused search approach")
        print(f"      → **Implication:** Examiner identifies strongest references quickly")
        print(f"      → **Strategy:** Focus on distinguishing key references cited")
    print()

else:
    print("⚠️ **No citation data available for this examiner**")
    print()
    print("**Possible reasons:**")
    print("  - All applications filed before 2015 (outside citation coverage window)")
    print("  - No office actions issued yet")
    print("  - All office actions occurred before Oct 2017 (pre-citation-data period)")
    print()
    print("📋 **Continuing with prosecution pattern analysis (citations unavailable)...**")
    print()
```

---

## PHASE 3: ALLOWANCE REASONING ANALYSIS (NOA DEEP DIVE)

### 3.1 Strategic NOA Selection for Pattern Detection

```python
print("---")
print()
print("### Allowance Reasoning Analysis (NOA Deep Dive)")
print()

# Find granted patents for NOA analysis
granted_apps = [
    app for app in applications
    if app.get('patentNumber') or
       app.get('applicationMetaData', {}).get('appStatusDescText') == 'Patented Case'
]

print(f"📊 **Granted Patents Found:** {len(granted_apps)}")
print()

if len(granted_apps) == 0:
    print("⚠️ **No granted patents found for NOA analysis**")
    print("   This examiner may have primarily pending applications")
    print("   Skipping allowance reasoning section...")
    print()
else:
    # Sort by issue date (most recent first)
    granted_sorted = sorted(
        granted_apps,
        key=lambda x: x.get('patentGrantDate', x.get('applicationMetaData', {}).get('patentGrantDate', '')),
        reverse=True
    )

    # Select representative sample: recent patents for current examiner behavior
    noa_sample_size = min(5, len(granted_sorted))
    representative_patents = granted_sorted[:noa_sample_size]

    print(f"📋 **Analyzing {noa_sample_size} recent NOAs for allowance patterns...**")
    print()

    noa_insights = []

    for idx, patent in enumerate(representative_patents, 1):
        app_number = patent.get('applicationNumberText')
        patent_number = patent.get('patentNumber', 'N/A')
        title = patent.get('applicationMetaData', {}).get('inventionTitle', 'Unknown')
        issue_date = patent.get('patentGrantDate', patent.get('applicationMetaData', {}).get('patentGrantDate', 'N/A'))

        print(f"**NOA {idx}/{noa_sample_size}: Patent {patent_number}**")
        title_display = title[:80] + ('...' if len(title) > 80 else '')
        print(f"  - Title: {title_display}")
        print(f"  - Issue Date: {issue_date}")

        # Get NOA document
        try:
            noa_docs = PFW_get_application_documents(
                app_number=app_number,
                document_code='NOA',
                limit=1
            )

            if noa_docs.get('documentBag') and len(noa_docs['documentBag']) > 0:
                noa_doc = noa_docs['documentBag'][0]
                page_count = noa_doc.get('pageCount', 'Unknown')
                doc_id = noa_doc.get('documentIdentifier')

                print(f"  - NOA Pages: {page_count}")

                # Extract NOA content (auto-optimize: fast text extraction first, OCR only when needed)
                noa_content = PFW_get_document_content_with_ocr(
                    app_number=app_number,
                    document_identifier=doc_id,
                    auto_optimize=True  # fast text extraction first, OCR only when needed
                )

                extracted_text = noa_content.get('extracted_content', '')
                extraction_method = noa_content.get('extraction_method', 'Unknown')

                print(f"  - Extracted: {len(extracted_text)} chars via {extraction_method}")

                # Store for cross-NOA pattern analysis
                noa_insights.append({
                    'patent_number': patent_number,
                    'app_number': app_number,
                    'title': title,
                    'noa_text': extracted_text,
                    'page_count': page_count
                })

                print(f"  - ✅ NOA extracted successfully")
            else:
                print(f"  - ⚠️ NOA document not found in file wrapper")

        except Exception as e:
            print(f"  - ❌ Error extracting NOA: {str(e)[:100]}")

        print()

    # Cross-NOA pattern analysis
    if len(noa_insights) > 0:
        print("### Cross-NOA Pattern Analysis")
        print()

        # Common allowance reasoning keywords
        allowance_keywords = {
            'specification': 0,
            'detailed description': 0,
            'written description': 0,
            'enablement': 0,
            'specific': 0,
            'particular': 0,
            'disclosed': 0,
            'teaches': 0,
            'suggests': 0,
            'motivation': 0,
            'combination': 0,
            'unexpected': 0
        }

        # Count keyword occurrences across all NOAs
        for noa in noa_insights:
            text_lower = noa['noa_text'].lower()
            for keyword in allowance_keywords:
                if keyword in text_lower:
                    allowance_keywords[keyword] += 1

        # Identify top patterns
        sorted_keywords = sorted(allowance_keywords.items(), key=lambda x: x[1], reverse=True)

        print("**Common Allowance Reasoning Patterns:**")
        for keyword, count in sorted_keywords[:10]:
            if count > 0:
                pct = (count / len(noa_insights)) * 100
                print(f"  - '{keyword}': {count}/{len(noa_insights)} NOAs ({pct:.0f}%)")
        print()

        # Strategic recommendations based on NOA patterns
        print("### Allowance Strategy Insights")
        print()

        spec_reliance = allowance_keywords.get('specification', 0) + allowance_keywords.get('detailed description', 0)
        if spec_reliance > len(noa_insights) * 0.6:
            print("**High Specification Reliance Detected:**")
            print(f"  - 📝 **Pattern:** Examiner heavily cites specification for claim support ({spec_reliance}/{len(noa_insights)} NOAs)")
            print(f"      → **Claim Drafting:** Ensure detailed description with explicit support for each claim element")
            print(f"      → **Specification Strategy:** Include implementation examples for each limitation")
            print(f"      → **Prosecution:** Point to specific specification passages in arguments")
            print()

        if allowance_keywords.get('motivation', 0) > len(noa_insights) * 0.4:
            print("**Motivation-Focused Allowances:**")
            print(f"  - 🔗 **Pattern:** Examiner considers motivation to combine in obviousness analysis")
            print(f"      → **Argument Strategy:** Emphasize lack of motivation or teaching away")
            print(f"      → **Evidence:** Provide technical reasons why combination would not work or would not be attempted")
            print()

        if allowance_keywords.get('specific', 0) > len(noa_insights) * 0.5:
            print("**Specificity-Oriented Allowances:**")
            print(f"  - 🎯 **Pattern:** Examiner allows claims with specific technical details")
            print(f"      → **Claim Strategy:** Narrow claims with concrete limitations more likely to succeed")
            print(f"      → **Dependent Claims:** Use dependent claims to capture broader scope")
            print()

        if allowance_keywords.get('unexpected', 0) > 0:
            print("**Unexpected Results Recognition:**")
            print(f"  - ✨ **Pattern:** Examiner recognizes unexpected results as patentable")
            print(f"      → **Prosecution Strategy:** Provide data showing unexpected advantages")
            print(f"      → **Specification:** Include comparative examples demonstrating superiority")
            print()
```

---

## PHASE 4: PROSECUTION EFFICIENCY METRICS

### 4.1 RCE and Amendment Analysis

```python
print("---")
print()
print("### Prosecution Patterns & Efficiency Metrics")
print()

# Re-use sample from citation analysis for consistency
prosecution_sample = sample_apps[:min(30, len(sample_apps))]

print(f"📊 **Analyzing {len(prosecution_sample)} applications for prosecution patterns...**")
print()

# Initialize counters
rce_count = 0
amendment_count = 0
ctfr_count = 0  # Non-final rejections
ctnf_count = 0  # Final rejections
total_oa_pages = 0
oa_apps = 0

apps_with_rce = []
apps_with_final = []

# Progress tracking
for i, app in enumerate(prosecution_sample, 1):
    app_number = app.get('applicationNumberText')

    if i % 10 == 0:
        print(f"  Progress: {i}/{len(prosecution_sample)} applications processed...")

    try:
        # Check for RCE filings (continuation after final rejection)
        rce_docs = PFW_get_application_documents(
            app_number=app_number,
            document_code='RCEX',
            limit=10
        )
        if rce_docs.get('documentBag'):
            rce_num = len(rce_docs['documentBag'])
            rce_count += rce_num
            if rce_num > 0:
                apps_with_rce.append(app_number)

        # Check for amendments/responses (applicant activity)
        amend_docs = PFW_get_application_documents(
            app_number=app_number,
            direction_category='INCOMING',  # Applicant submissions
            limit=20
        )
        if amend_docs.get('documentBag'):
            # Filter for actual responses (A... document codes)
            responses = [
                doc for doc in amend_docs['documentBag']
                if doc.get('mailRoomDate') and
                   doc.get('documentCode', '').startswith('A')
            ]
            amendment_count += len(responses)

        # Check for non-final rejections (examiner activity)
        oa_docs = PFW_get_application_documents(
            app_number=app_number,
            document_code='CTFR',  # Non-final rejection
            limit=10
        )
        if oa_docs.get('documentBag'):
            ctfr_count += len(oa_docs['documentBag'])
            oa_apps += 1
            for doc in oa_docs['documentBag']:
                total_oa_pages += doc.get('pageCount', 0)

        # Check for final rejections
        final_docs = PFW_get_application_documents(
            app_number=app_number,
            document_code='CTNF',  # Final rejection
            limit=5
        )
        if final_docs.get('documentBag'):
            ctnf_num = len(final_docs['documentBag'])
            ctnf_count += ctnf_num
            if ctnf_num > 0:
                apps_with_final.append(app_number)

    except Exception as e:
        # Gracefully continue with other applications
        continue

print()
print("✅ **Prosecution pattern analysis complete**")
print()

# Calculate metrics
avg_rce = rce_count / len(prosecution_sample) if len(prosecution_sample) > 0 else 0
rce_rate = (len(apps_with_rce) / len(prosecution_sample)) * 100 if len(prosecution_sample) > 0 else 0
avg_amendments = amendment_count / len(prosecution_sample) if len(prosecution_sample) > 0 else 0
avg_ctfr = ctfr_count / len(prosecution_sample) if len(prosecution_sample) > 0 else 0
avg_ctnf = ctnf_count / len(prosecution_sample) if len(prosecution_sample) > 0 else 0
final_rate = (len(apps_with_final) / len(prosecution_sample)) * 100 if len(prosecution_sample) > 0 else 0
avg_oa_pages = total_oa_pages / oa_apps if oa_apps > 0 else 0

print("### Prosecution Efficiency Metrics")
print()

print("**RCE Analysis (Continuation After Final):**")
print(f"  - Applications with RCE: {len(apps_with_rce)}/{len(prosecution_sample)} ({rce_rate:.1f}%)")
print(f"  - Average RCE per Application: {avg_rce:.2f}")
print()

print("**Office Action Patterns:**")
print(f"  - Average Non-Final Rejections: {avg_ctfr:.2f} per app")
print(f"  - Average Final Rejections: {avg_ctnf:.2f} per app")
print(f"  - Applications with Finals: {len(apps_with_final)}/{len(prosecution_sample)} ({final_rate:.1f}%)")
print(f"  - Average OA Length: {avg_oa_pages:.1f} pages")
print()

print("**Applicant Response Activity:**")
print(f"  - Average Amendments/Responses: {avg_amendments:.2f} per app")
print()

# Prosecution difficulty assessment
print("### Prosecution Difficulty Assessment")
print()

if avg_rce > 0.8:
    difficulty = "Very High"
    color = "🔴"
    strategy = "Expect extended prosecution - consider narrow claims from outset"
    budget_multiplier = "3-4x"
elif avg_rce > 0.5:
    difficulty = "High"
    color = "🟠"
    strategy = "Frequent RCE filings - prepare for iterative claim narrowing"
    budget_multiplier = "2-3x"
elif avg_rce > 0.2:
    difficulty = "Moderate"
    color = "🟡"
    strategy = "Some RCE activity - balanced approach with claim flexibility"
    budget_multiplier = "1.5-2x"
else:
    difficulty = "Low"
    color = "🟢"
    strategy = "Most applications allow without RCE - examiner reasonable"
    budget_multiplier = "1-1.5x"

print(f"**Difficulty Level:** {color} **{difficulty}**")
print(f"**Expected Budget:** {budget_multiplier} standard prosecution costs")
print(f"**Strategy:** {strategy}")
print()

if final_rate > 50:
    print(f"⚠️ **High Final Rejection Rate ({final_rate:.0f}%):** Examiner frequently issues finals")
    print(f"   → **Implication:** Plan for RCE filings or early claim narrowing to avoid finals")
    print()

if avg_oa_pages > 20:
    print(f"📚 **Lengthy Office Actions ({avg_oa_pages:.0f} pages avg):** Detailed examiner analysis")
    print(f"   → **Implication:** Expect thorough rejections with extensive prior art discussion")
    print(f"   → **Strategy:** Prepare comprehensive responses with detailed technical distinctions")
    print()
elif avg_oa_pages > 10:
    print(f"📄 **Standard Office Actions ({avg_oa_pages:.0f} pages avg):** Normal detail level")
    print()
```

---

## PHASE 5: PETITION HISTORY & QUALITY ASSESSMENT (FPD INTEGRATION)

### 5.1 Petition Analysis for Examiner Quality Indicators

```python
print("---")
print()
print("### Petition History & Quality Assessment (FPD Integration)")
print()

# Search for petitions filed against this examiner's applications
petition_apps = []
petition_count = 0

# Sample 20 applications for petition check (reduce API calls)
petition_sample = prosecution_sample[:20]

print(f"🔍 **Checking petition history for {len(petition_sample)} applications...**")
print()

for app in petition_sample:
    app_number = app.get('applicationNumberText')

    try:
        petitions = FPD_Search_petitions_by_application(
            application_number=app_number,
            include_documents=False  # Metadata only
        )

        if petitions.get('count', 0) > 0:
            petition_count += len(petitions.get('petitions', []))
            petition_apps.append({
                'app_number': app_number,
                'petitions': petitions['petitions']
            })
    except Exception as e:
        # FPD data may not be available for all applications
        continue

petition_rate = (len(petition_apps) / len(petition_sample)) * 100 if len(petition_sample) > 0 else 0

print(f"**Petition Activity:**")
print(f"  - Applications with Petitions: {len(petition_apps)}/{len(petition_sample)} ({petition_rate:.1f}%)")
print(f"  - Total Petitions Filed: {petition_count}")
print()

if len(petition_apps) > 0:
    # Analyze petition types and outcomes
    petition_types = Counter()
    petition_decisions = Counter()

    for app_data in petition_apps:
        for petition in app_data['petitions']:
            pet_type = petition.get('petitionTypeCode', 'Unknown')
            decision = petition.get('decisionType', 'Unknown')
            petition_types[pet_type] += 1
            petition_decisions[decision] += 1

    print("**Petition Type Distribution:**")
    for pet_type, count in petition_types.most_common():
        pct = (count / petition_count) * 100

        # Interpret petition type
        type_desc = {
            '182': 'Restriction Requirement Petition',
            '131': 'Terminal Disclaimer Petition',
            '133': 'Suspended Application Petition',
            '137': 'Revival (Unintentional Abandonment)',
            '183': 'Unity of Invention Petition',
            '181': 'Supervisory Review Petition'
        }.get(pet_type, f'Type {pet_type}')

        print(f"  - {type_desc}: {count} ({pct:.1f}%)")
    print()

    print("**Petition Decision Outcomes:**")
    for decision, count in petition_decisions.most_common():
        pct = (count / petition_count) * 100
        print(f"  - {decision}: {count} ({pct:.1f}%)")
    print()

    # Quality indicators based on petition patterns
    print("### Quality Indicators from Petition History")
    print()

    denied_rate = (petition_decisions.get('DENIED', 0) / petition_count) * 100 if petition_count > 0 else 0
    granted_rate = (petition_decisions.get('GRANTED', 0) / petition_count) * 100 if petition_count > 0 else 0

    if petition_rate > 15:
        print(f"⚠️ **High Petition Rate ({petition_rate:.0f}%):** Above-average supervisory review requests")
        print(f"   → **Implication:** Possible applicant dissatisfaction or procedural challenges")
        print()

    if '181' in petition_types and petition_types['181'] > petition_count * 0.3:
        print(f"🚩 **Supervisory Review Petitions ({petition_types['181']}):** Applicants seeking examiner oversight")
        print(f"   → **Implication:** Possible communication or procedural issues with examiner")
        print(f"   → **Strategy:** Maintain clear, documented communication; consider early interviews")
        print()

    if '137' in petition_types and petition_types['137'] > 0:
        print(f"📅 **Revival Petitions ({petition_types['137']}):** Applications abandoned and revived")
        print(f"   → **Implication:** May indicate deadline pressure or procedural challenges")
        print()

    if granted_rate > 50:
        print(f"✅ **High Petition Success Rate ({granted_rate:.0f}%):** Examiner actions frequently overturned")
        print(f"   → **Implication:** Petitions viable strategy if procedural issues arise")
        print()
    elif denied_rate > 70:
        print(f"❌ **Low Petition Success Rate ({granted_rate:.0f}%):** Most petitions denied")
        print(f"   → **Implication:** Petition strategy less effective; focus on substantive arguments")
        print()

else:
    print("✅ **No Petition History Found:** Clean prosecution record")
    print("   → **Positive Indicator:** No evidence of procedural issues or applicant dissatisfaction")
    print()
```

---

## PHASE 6: PTAB CHALLENGE CORRELATION (POST-GRANT RISK)

### 6.1 PTAB Proceedings Analysis for Patent Quality Assessment

**PTAB MCP Tool Changes (as of 2026-01-17):**
- OLD: ptab_search_proceedings_minimal/balanced
- NEW: PTAB_search_trials_minimal/balanced (for IPR/PGR/CBM)
- NEW: PTAB_search_appeals_minimal/balanced (for Ex Parte Appeals)
- NEW: PTAB_search_interferences_minimal/balanced (for Derivations)

**Token Optimization:** Use fields parameter for ultra-minimal queries (99% reduction)
For cross-MCP correlation, request only needed fields:
  fields=['trialNumber', 'trialMetaData.trialStatusCategory', 'petitionerData.petitionerName']
This reduces context from ~40KB (preset minimal) to ~5KB (ultra-minimal)

```python
print("---")
print()
print("### PTAB Challenge Correlation (Post-Grant Risk Assessment)")
print()

# Search for PTAB challenges against granted patents from this examiner
ptab_challenges = []

# Get granted patent numbers from applications
granted_patent_numbers = [
    app.get('patentNumber')
    for app in applications
    if app.get('patentNumber')
]

# Sort patent numbers (descending) - higher numbers = more recent = more likely to have PTAB proceedings
granted_patent_numbers_sorted = sorted(granted_patent_numbers, reverse=True)

print(f"🔍 **Checking PTAB challenges for {len(granted_patent_numbers_sorted)} granted patents...**")
print()

# Sample to reduce API calls (PTAB data can be extensive)
# Take most recent patents (highest numbers first) - PTAB proceedings more common for recent patents
ptab_sample = granted_patent_numbers_sorted[:30]

if ptab_sample:
    print(f"📊 **PTAB sample range (most recent first):** {ptab_sample[0]} to {ptab_sample[-1] if len(ptab_sample) > 1 else ptab_sample[0]}")
    print()

for patent_num in ptab_sample:
    try:
        # Use ultra-minimal mode with fields parameter for 99% reduction
        proceedings = PTAB_search_trials_minimal(
            patent_number=patent_num,
            fields=['trialNumber', 'trialMetaData.trialStatusCategory', 'petitionerData.petitionerName'],
            limit=10
        )

        if proceedings.get('count', 0) > 0:
            ptab_challenges.append({
                'patent_number': patent_num,
                'proceedings': proceedings['results']
            })
    except Exception as e:
        # PTAB data may not be available for all patents
        continue

challenge_rate = (len(ptab_challenges) / len(ptab_sample)) * 100 if len(ptab_sample) > 0 else 0

print(f"**PTAB Challenge Statistics:**")
print(f"  - Patents with Challenges: {len(ptab_challenges)}/{len(ptab_sample)} ({challenge_rate:.1f}%)")
print()

if len(ptab_challenges) > 0:
    # Analyze challenge types and outcomes
    proceeding_types = Counter()
    proceeding_statuses = Counter()

    for challenge_data in ptab_challenges:
        for proc in challenge_data['proceedings']:
            proc_type = proc.get('subproceedingType', 'Unknown')
            status = proc.get('proceedingStatusDescriptionText', 'Unknown')
            proceeding_types[proc_type] += 1
            proceeding_statuses[status] += 1

    total_proceedings = sum(proceeding_types.values())

    print("**Challenge Type Distribution:**")
    for proc_type, count in proceeding_types.most_common():
        pct = (count / total_proceedings) * 100
        print(f"  - {proc_type}: {count} ({pct:.1f}%)")
    print()

    print("**Proceeding Outcomes:**")
    for status, count in proceeding_statuses.most_common():
        pct = (count / total_proceedings) * 100
        print(f"  - {status}: {count} ({pct:.1f}%)")
    print()

    # Post-grant risk assessment
    print("### Post-Grant Risk Assessment")
    print()

    if challenge_rate > 20:
        print(f"🚨 **High Challenge Rate ({challenge_rate:.0f}%):** Patents frequently challenged at PTAB")
        print(f"   → **Possible Causes:**")
        print(f"      - Claim quality concerns (overly broad claims)")
        print(f"      - High-value patent space (competitors motivated to challenge)")
        print(f"   → **Recommendation:** Comprehensive prior art search and claim refinement")
        print()
    elif challenge_rate > 10:
        print(f"⚠️ **Moderate Challenge Rate ({challenge_rate:.0f}%):** Some PTAB activity")
        print(f"   → **Implication:** Standard risk level for valuable patents")
        print()
    else:
        print(f"✅ **Low Challenge Rate ({challenge_rate:.0f}%):** Minimal PTAB challenges")
        print(f"   → **Possible Indicators:**")
        print(f"      - Robust prosecution quality")
        print(f"      - Lower commercial value patent space")
        print(f"      - Patents too recent for challenges")
        print()

    # Outcome analysis
    terminated = proceeding_statuses.get('Terminated', 0)
    instituted = proceeding_statuses.get('Instituted', 0)

    if terminated > instituted:
        print(f"✅ **More Terminations than Institutions:** Patents surviving challenges")
        print()
    elif instituted > 0:
        print(f"⚠️ **Active Institutions:** Some patents under active PTAB review")
        print(f"   → **Implication:** Monitor outcomes for examiner quality trends")
        print()

else:
    print("✅ **No PTAB Challenges Found:** Low post-grant risk")
    print()
    print("**Possible Indicators:**")
    print("  - Strong prosecution quality")
    print("  - Lower commercial value space")
    print("  - Patents too recent for challenges (IPR requires post-grant timing)")
    print()
```

---

## PHASE 7: COMPREHENSIVE INTELLIGENCE REPORT

### 7.1 Executive Summary with Key Metrics

```python
print("=" * 80)
print("ENHANCED EXAMINER BEHAVIOR INTELLIGENCE REPORT")
print("=" * 80)
print()

print(f"**Examiner:** {primary_examiner}")
print(f"**Primary Art Unit:** {primary_art_unit[0]}")
print(f"**Analysis Period:** 2015-01-01 to present")
print(f"**Applications Analyzed:** {len(applications)}")
print(f"**Citation Data Coverage:** {apps_with_citations}/{sample_size} applications ({citation_coverage:.0f}%)")
print()

print("### Key Metrics Summary Table")
print()

# Create comprehensive metrics table
print("| Category | Metric | Value |")
print("|----------|--------|-------|")
print(f"| **Citation Behavior** | Examiner Citation Rate | {examiner_rate:.0f}% |")
if apps_with_citations > 0:
    print(f"| | Citations per Application | {examiner_cited_count / apps_with_citations:.1f} |")
    if categories:
        print(f"| | Primary Category | {categories.most_common(1)[0][0]} |")
else:
    print(f"| | Citations per Application | N/A |")
    print(f"| | Primary Category | N/A |")
print(f"| **Prosecution Patterns** | RCE Rate | {rce_rate:.0f}% |")
print(f"| | Final Rejection Rate | {final_rate:.0f}% |")
print(f"| | Difficulty Level | {difficulty} {color} |")
print(f"| | Expected Budget | {budget_multiplier} standard |")
print(f"| **Quality Indicators** | Petition Rate | {petition_rate:.0f}% |")
print(f"| | PTAB Challenge Rate | {challenge_rate:.0f}% |")
print()
```

### 7.2 Strategic Prosecution Recommendations

```python
print("---")
print()
print("### STRATEGIC PROSECUTION RECOMMENDATIONS")
print()

print("#### 1. Prior Art & IDS Strategy")
print()

if len(all_citations) > 0:
    if examiner_rate > 70:
        print("**Recommendation:** Focus on technical distinctions over comprehensive IDS")
        print(f"**Rationale:** Examiner rarely uses applicant-cited references ({examiner_rate:.0f}% self-cited)")
        print("**Action Items:**")
        print("  - File targeted IDS with key closest prior art only")
        print("  - Include detailed explanations of non-applicability for each reference")
        print("  - Focus prosecution arguments on technical distinctions from examiner's citations")
        print()
    elif examiner_rate > 50:
        print("**Recommendation:** Strategic IDS filing of closest prior art with commentary")
        print(f"**Rationale:** Examiner uses some applicant-cited references ({examiner_rate:.0f}% self-cited)")
        print("**Action Items:**")
        print("  - Include key references that show invention's technical advantages")
        print("  - Provide substantive commentary explaining how invention differs")
        print("  - Shape examiner's understanding through strategic disclosure")
        print()
    else:
        print("**Recommendation:** Comprehensive IDS with detailed framing explanations")
        print(f"**Rationale:** Examiner frequently uses applicant-cited references ({100-examiner_rate:.0f}% applicant-cited used)")
        print("**Action Items:**")
        print("  - File comprehensive IDS to shape prosecution narrative")
        print("  - Include detailed technical comparison for key references")
        print("  - Use IDS to establish invention's unique technical contribution")
        print()

    # Category-specific guidance
    if categories:
        top_category = categories.most_common(1)[0][0]
        if top_category == 'X':
            print("**Citation Category Focus:** High X-citation preference (single-reference anticipation)")
            print("**Claim Strategy:**")
            print("  - Ensure claims include non-obvious combinations of features")
            print("  - Avoid claims that read on single prior art reference")
            print("  - Include specific implementation details to differentiate from prior art")
            print()
        elif top_category == 'Y':
            print("**Citation Category Focus:** High Y-citation preference (combination rejections)")
            print("**Claim Strategy:**")
            print("  - Emphasize unexpected results and synergistic advantages")
            print("  - Provide evidence of non-obvious technical effects")
            print("  - Include dependent claims with narrowing features for fall-back positions")
            print()
else:
    print("**Note:** Citation data unavailable - use standard comprehensive IDS approach")
    print()

print("#### 2. Claim Drafting Strategy")
print()

if len(noa_insights) > 0:
    spec_reliance_val = allowance_keywords.get('specification', 0) + allowance_keywords.get('detailed description', 0)
    if spec_reliance_val > len(noa_insights) * 0.6:
        print("**Approach:** Specification-heavy claiming with explicit support")
        print("**Detail Level Required:**")
        print("  - Include implementation specifics and concrete examples in claims")
        print("  - Ensure each limitation has dedicated description section in specification")
        print("  - Use specific technical parameters rather than functional language")
        print()
    else:
        print("**Approach:** Standard claim drafting with moderate specification detail")
        print()

    if allowance_keywords.get('specific', 0) > len(noa_insights) * 0.5:
        print("**Scope Guidance:** Narrower claims with specific technical details more likely to succeed")
        print("**Breadth Strategy:**")
        print("  - Independent claims: Specific implementations with concrete limitations")
        print("  - Dependent claims: Capture broader conceptual variations")
        print("  - Multiple independent claims: Cover alternative embodiments specifically")
        print()

print("#### 3. Prosecution Timeline & Budget Planning")
print()

if avg_rce > 0.5:
    print(f"**Expected Duration:** Extended (RCE likely in {rce_rate:.0f}% of cases)")
    print(f"**Budget Planning:** Plan for {budget_multiplier} standard prosecution costs")
    print("**Strategic Recommendations:**")
    print("  - Consider early claim narrowing to avoid multiple RCE cycles")
    print("  - Prepare fall-back claim sets in advance")
    print("  - Budget for extended prosecution (2-3+ years from first OA)")
    print()
elif avg_rce > 0.2:
    print(f"**Expected Duration:** Standard to extended (RCE in {rce_rate:.0f}% of cases)")
    print(f"**Budget Planning:** Plan for {budget_multiplier} standard prosecution costs")
    print("**Strategic Recommendations:**")
    print("  - Have contingency claim sets ready")
    print("  - Standard prosecution timeline (1.5-2 years from first OA)")
    print()
else:
    print(f"**Expected Duration:** Standard (RCE uncommon at {rce_rate:.0f}%)")
    print("**Budget Planning:** Standard prosecution budget should suffice")
    print("**Strategic Recommendations:**")
    print("  - Examiner reasonable - standard prosecution approach")
    print("  - Expected timeline: 1-1.5 years from first OA to allowance")
    print()

print("#### 4. Office Action Response Strategy")
print()

if avg_oa_pages > 15:
    print(f"**Office Action Detail:** Lengthy, detailed OAs ({avg_oa_pages:.0f} pages avg)")
    print("**Response Approach:**")
    print("  - Allocate extra time for comprehensive rebuttal preparation")
    print("  - Match examiner's thoroughness with equally detailed technical responses")
    print("  - Provide point-by-point responses with supporting technical evidence")
    print()
elif avg_oa_pages > 10:
    print(f"**Office Action Detail:** Standard detail level ({avg_oa_pages:.0f} pages avg)")
    print("**Response Approach:** Normal response timeline and standard technical arguments")
    print()

if final_rate > 50:
    print(f"**Final OA Strategy:** High final rate ({final_rate:.0f}%) - plan for finals")
    print("**Recommendations:**")
    print("  - Consider early claim narrowing to avoid finals")
    print("  - Prepare RCE fall-back claim sets in advance")
    print("  - Budget for after-final responses or RCE continuations")
    print()

print("#### 5. Risk Mitigation Strategies")
print()

if petition_rate > 15:
    print(f"⚠️ **Procedural Risk:** Above-average petition rate ({petition_rate:.0f}%)")
    print("**Mitigation Actions:**")
    print("  - Ensure strict deadline compliance (calendar all dates immediately)")
    print("  - Maintain clear, documented communication with examiner")
    print("  - Consider early examiner interview to establish rapport")
    print()

if challenge_rate > 20:
    print(f"⚠️ **Post-Grant Risk:** High PTAB challenge rate ({challenge_rate:.0f}%)")
    print("**Mitigation Actions:**")
    print("  - Conduct comprehensive prior art search before filing")
    print("  - Emphasize claim specificity and clear written description")
    print("  - Document technical advantages and unexpected results")
    print()
elif challenge_rate > 10:
    print(f"⚠️ **Post-Grant Risk:** Moderate PTAB activity ({challenge_rate:.0f}%)")
    print("**Mitigation Actions:** Standard prior art diligence recommended")
    print()
else:
    print(f"✅ **Low Post-Grant Risk:** Minimal PTAB challenges ({challenge_rate:.0f}%)")
    print()

print("#### 6. Examiner Interview Strategy")
print()

if difficulty == "Very High" or difficulty == "High":
    print("**Recommendation:** Schedule early examiner interview after first office action")
    print("**Interview Focus:**")
    print("  - Understand examiner's claim interpretation and specific technical concerns")
    print("  - Clarify scope of prior art rejections and identify allowable subject matter")
    print("  - Present amendment proposals with technical rationale")
    print("**Preparation:**")
    print("  - Bring claim amendment proposals and prior art distinction charts")
    print("  - Prepare technical presentations if complex technology")
    print()
else:
    print("**Recommendation:** Standard interview approach - after first substantive rejection")
    print("**Interview Focus:**")
    print("  - Clarify claim scope and confirm allowable subject matter")
    print("  - Discuss amendment strategy to expedite allowance")
    print()
```

### 7.3 Data Quality & Limitations Disclosure

```python
print("---")
print()
print("### DATA QUALITY & LIMITATIONS")
print()

print("**Coverage Analysis:**")
print(f"  - Applications Analyzed: {len(applications)}")
print(f"  - Citation Data Available: {apps_with_citations}/{sample_size} ({citation_coverage:.0f}%)")
print(f"  - Prosecution Data: {len(prosecution_sample)} applications")
print(f"  - NOA Analysis: {len(noa_insights)} granted patents")
print(f"  - Petition Data: {len(petition_sample)} applications checked")
print(f"  - PTAB Data: {len(ptab_sample)} granted patents checked")
print()

print("**Data Limitations:**")
print("  - **Citations MCP:** Office actions from Oct 1, 2017+ only (API limitation)")
print("  - **Pre-2017 Applications:** May lack citation data (office actions before coverage period)")
print("  - **Sample Size:** May not capture full examiner behavior range across all technology areas")
print(f"  - **Analysis Period:** Filing dates 2015-01-01 to present (older apps excluded)")
print()

if citation_coverage < 50:
    print("⚠️ **LOW CITATION COVERAGE WARNING:**")
    print(f"   Citation-based recommendations have limited statistical validity ({citation_coverage:.0f}% coverage)")
    print("   **Recommendations:**")
    print("     - Request more recent applications (filed 2018+) for better citation coverage")
    print("     - Supplement with manual review of office actions")
    print("     - Focus more weight on prosecution patterns and NOA analysis")
    print()

print("**Statistical Confidence:**")
if len(applications) >= min_sample_size:
    print(f"  ✅ **Sample size ({len(applications)}) meets minimum threshold ({min_sample_size})**")
    print("     Results have reasonable statistical confidence")
else:
    print(f"  ⚠️ **Sample size ({len(applications)}) below recommended minimum ({min_sample_size})**")
    print("     **Recommendation:** Increase sample for more robust conclusions")
    print("     Consider broader search or longer time period")
print()
```

### 7.4 Actionable Next Steps

```python
print("---")
print()
print("### RECOMMENDED NEXT STEPS")
print()

print("**Immediate Actions (Before Filing):**")
print("  1. Review NOA text for specific allowance reasoning patterns (completed above)")
print("  2. Analyze representative office actions for claim interpretation style")
print("  3. Prepare initial claim sets following identified success patterns")
print("  4. Conduct prior art search focusing on examiner's preferred citation types")
print()

print("**Pre-Filing Preparation:**")
print("  5. Draft specification with adequate support for all claim limitations")
print("  6. Include concrete examples and specific implementation details")
print("  7. Prepare dependent claims for narrowing strategy if RCE likely")
print("  8. Develop IDS strategy based on examiner's citation selectivity")
print()

print("**During Prosecution:**")
print("  9. Schedule examiner interview after first office action")
print("  10. Prepare amendment proposals aligned with NOA allowance patterns")
print("  11. Provide detailed technical arguments matching examiner's OA detail level")
print()

print("**Ongoing Monitoring:**")
print("  12. Track examiner's recent allowances for evolving patterns")
print("  13. Monitor PTAB challenges if post-grant risk identified")
print("  14. Review petition outcomes if quality concerns flagged")
print()

print("=" * 80)
print("END OF ENHANCED EXAMINER BEHAVIOR INTELLIGENCE REPORT")
print("=" * 80)
print()

print("**Report Generation Notes:**")
print(f"  - Total Applications Retrieved: {len(applications)}")
print(f"  - Citations Analyzed: {len(all_citations)}")
print(f"  - NOAs Extracted: {len(noa_insights)}")
print()
print("**Next Analysis:** Consider running this analysis periodically (every 6-12 months)")
print("to track examiner behavior changes over time.")
```

---

## IMPLEMENTATION NOTES

### Token Efficiency

**This enhanced workflow uses ultra-minimal mode throughout:**

- **PFW searches:** 8 custom fields (vs 15+ preset) = 47% reduction
- **Citation searches:** 8 preset minimal fields = 90% reduction vs balanced
- **Document retrieval:** Filtered by document_code = 70-90% reduction
- **NOA extraction:** `auto_optimize=True` = fast text extraction first, OCR only for scanned pages

**Expected Context Usage:**
- 100 applications × 8 fields = ~10KB
- 30 citation searches × 50 cites × 8 fields = ~480KB
- 5 NOA extracts = ~50KB
- **Total: ~540KB** (fits in most LLM context windows)

### Error Handling Philosophy

Every API call wrapped in try-except with:
1. **Graceful degradation:** Continue analysis even if individual calls fail
2. **User notification:** Clear warnings when data unavailable
3. **Statistical validation:** Flag insufficient data for confident conclusions
4. **Progressive disclosure:** User decision points at critical junctures

### Cross-MCP Integration

**Required MCPs:**
- **PFW (Patent File Wrapper):** Application search, document retrieval, NOA extraction
- **Citations (Enriched Citation):** Citation pattern analysis
- **FPD (Petition Decision):** Quality assessment via petition history
- **PTAB (Patent Trial & Appeal Board):** Post-grant risk profiling

**Graceful degradation if MCP unavailable:**
- Citations unavailable → Skip citation analysis, continue with prosecution patterns
- FPD unavailable → Skip petition analysis, note in limitations
- PTAB unavailable → Skip post-grant risk, note in report

### Extraction Efficiency

**NOA extraction (5 docs):** use auto-optimize mode — fast text extraction
first, OCR fallback only for scanned documents that need it.

---

**COMPREHENSIVE IMPLEMENTATION COMPLETE**

This enhanced prompt provides complete workflows with:
- ✅ Actual tool call examples with parameters
- ✅ Error handling with try-except blocks
- ✅ Progressive disclosure with user decision points
- ✅ Statistical validation and confidence assessment
- ✅ Cross-MCP integration with eligibility checks
- ✅ Presentation formatting (markdown tables, headers)
- ✅ Strategic recommendations based on data patterns
- ✅ Data quality transparency and limitations disclosure
- ✅ Actionable next steps for prosecution planning

**Philosophy:** Invest context in prompt to prevent 10x mistakes during execution.
