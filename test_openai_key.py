#!/usr/bin/env python3
"""Quick test of OpenAI API key and LinkedIn profile parsing."""

import sys
from src.config import settings
from src.data.llm_parser import parse_linkedin_with_llm

# Sample LinkedIn profile text (minimal example)
SAMPLE_LINKEDIN = """
CTO at Acme Corp
2021 - Present · 3 years
Led engineering team of 15 engineers. Responsible for architecture and technical strategy.

VP Engineering at TechCorp
2018 - 2021 · 3 years
Managed 8-person engineering team. Built internal tooling platform.

Senior Software Engineer at StartupXYZ
2016 - 2018 · 2 years
Full-stack engineer. Owned backend infrastructure and DevOps.

Software Engineer at BigTech Inc
2014 - 2016 · 2 years
Built features for mobile platform. 500M+ users.
"""

def test_openai_key():
    """Test OpenAI API key with a simple LinkedIn profile parse."""

    print("=" * 70)
    print("OpenAI API Key Test")
    print("=" * 70)

    # Check if API key is set
    if not settings.openai_api_key:
        print("❌ ERROR: OPENAI_API_KEY not set in .env")
        print("   Add: OPENAI_API_KEY=sk-proj-... to .env")
        return False

    print(f"✓ OpenAI API Key found")
    print(f"✓ Using model: {settings.openai_model}")
    print()

    # Parse the sample LinkedIn profile
    print("Testing parse with sample LinkedIn profile...")
    print("-" * 70)

    try:
        positions = parse_linkedin_with_llm(SAMPLE_LINKEDIN)
        print(f"✓ Successfully parsed {len(positions)} positions")
        print()

        # Validate extracted positions
        valid_seniorities = {"founder", "vp-c-level", "managerial", "hands-on"}
        all_valid = True

        for i, pos in enumerate(positions, 1):
            print(f"Position {i}:")
            print(f"  Employer: {pos.get('employer_name', 'N/A')}")
            print(f"  Title: {pos.get('title', 'N/A')}")
            print(f"  Seniority: {pos.get('seniority', 'N/A')}", end="")

            # Validate seniority
            if pos.get('seniority') not in valid_seniorities:
                print(f" ❌ INVALID (must be one of {valid_seniorities})")
                all_valid = False
            else:
                print(" ✓")

            print(f"  Started: {pos.get('started_at', 'N/A')}")
            print(f"  Ended: {pos.get('ended_at', 'N/A')}")
            print(f"  Tenure: {pos.get('tenure_years', 0)} years")

            is_advisory = pos.get('is_advisory', False)
            print(f"  Is Advisory: {is_advisory}", end="")

            # is_advisory should be false for normal roles
            if is_advisory and pos.get('seniority') in {"founder", "vp-c-level", "managerial", "hands-on"}:
                print(" ⚠️  (should be false for non-advisory roles)")
                all_valid = False
            else:
                print(" ✓")
            print()

        # Validate first position is most recent
        if positions:
            first_title = positions[0].get('title', '')
            if 'CTO' in first_title or 'VP' in first_title:
                print("✓ First position is most recent (CTO/VP) ✓")
            else:
                print(f"⚠️  First position might not be most recent: {first_title}")

        print()
        print("=" * 70)
        if all_valid:
            print("✅ All validation checks PASSED")
            print("OpenAI integration is working correctly!")
            return True
        else:
            print("⚠️  Some validation checks failed")
            return False

    except RuntimeError as e:
        print(f"❌ ERROR: {e}")
        return False
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_openai_key()
    sys.exit(0 if success else 1)
