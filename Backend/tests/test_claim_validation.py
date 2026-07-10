from app.services.claim_validation import ClaimCategory, find_unsupported_claims


def test_claim_validation_blocks_high_risk_career_claim_categories():
    findings = find_unsupported_claims(
        (
            "I worked at Invented Corp as a senior certified engineer, served 1,000,000 users, "
            "drove 900% revenue growth, and managed 50 production deployments with 99.99% uptime."
        ),
        "Built a Python API for a university project.",
    )

    assert {finding.category for finding in findings} >= {
        ClaimCategory.metric,
        ClaimCategory.work_history,
        ClaimCategory.seniority,
        ClaimCategory.credential,
        ClaimCategory.scale,
        ClaimCategory.production_reliability,
    }


def test_claim_validation_allows_claims_present_in_evidence():
    evidence = (
        "Worked at Verified Corp as a senior certified engineer and supported 100 users through "
        "five production deployments with 99.9% uptime."
    )

    assert find_unsupported_claims(evidence, evidence) == []


def test_target_company_name_is_allowed_but_employment_claim_is_not():
    assert (
        find_unsupported_claims(
            "I am applying to Target Corp.",
            "Built a Python API.",
            allowed_organizations=("Target Corp",),
        )
        == []
    )

    findings = find_unsupported_claims(
        "I worked at Target Corp.",
        "Built a Python API.",
        allowed_organizations=("Target Corp",),
    )
    assert ClaimCategory.work_history in {finding.category for finding in findings}
