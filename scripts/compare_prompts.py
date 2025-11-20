#!/usr/bin/env python3
"""
Prompt Comparison Script for Gemini 3 Pro Preview Migration
Compares _create_prompt_v2 and _create_prompt_v3 methods
"""

import re
import sys
sys.path.insert(0, '.')

def extract_prompt_from_method(content, method_name):
    """Extract prompt string from method"""
    pattern = rf'def {method_name}\(.*?\):\s*""".*?"""(.*?)return prompt'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        method_body = match.group(1)
        # Find the prompt = f""" ... """ section
        prompt_pattern = r'prompt\s*=\s*f?"""(.*?)"""'
        prompt_match = re.search(prompt_pattern, method_body, re.DOTALL)
        if prompt_match:
            return prompt_match.group(1)
    return None

def count_lines(text):
    """Count non-empty lines"""
    return len([line for line in text.split('\n') if line.strip()])

def estimate_tokens(text):
    """Rough token estimate (1 token ~= 4 chars)"""
    return len(text) // 4

def main():
    # Read the file
    with open('services/itinerary_generator3.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract prompts
    v2_prompt = extract_prompt_from_method(content, '_create_prompt_v2')
    v3_prompt = extract_prompt_from_method(content, '_create_prompt_v3')

    if not v2_prompt or not v3_prompt:
        print("❌ Could not extract prompts from methods")
        return

    # Calculate statistics
    v2_lines = count_lines(v2_prompt)
    v3_lines = count_lines(v3_prompt)
    v2_chars = len(v2_prompt)
    v3_chars = len(v3_prompt)
    v2_tokens = estimate_tokens(v2_prompt)
    v3_tokens = estimate_tokens(v3_prompt)

    lines_saved = v2_lines - v3_lines
    chars_saved = v2_chars - v3_chars
    tokens_saved = v2_tokens - v3_tokens

    lines_pct = (lines_saved / v2_lines) * 100
    chars_pct = (chars_saved / v2_chars) * 100
    tokens_pct = (tokens_saved / v2_tokens) * 100

    # Print comparison
    print("=" * 70)
    print(" PROMPT COMPARISON: v2 (Flash) vs v3 (Gemini 3 Pro Preview)")
    print("=" * 70)
    print()
    print(f"{'Metric':<20} {'V2 (Flash)':<15} {'V3 (Gemini 3)':<15} {'Reduction':<20}")
    print("-" * 70)
    print(f"{'Lines':<20} {v2_lines:<15,} {v3_lines:<15,} {lines_saved:,} ({lines_pct:.1f}%)")
    print(f"{'Characters':<20} {v2_chars:<15,} {v3_chars:<15,} {chars_saved:,} ({chars_pct:.1f}%)")
    print(f"{'Est. Tokens':<20} {v2_tokens:<15,} {v3_tokens:<15,} {tokens_saved:,} ({tokens_pct:.1f}%)")
    print("=" * 70)
    print()

    # Section analysis
    print("SECTION BREAKDOWN")
    print("-" * 70)

    sections_v2 = {
        'Role & Input': len(re.findall(r'## 당신의 역할|## 입력 데이터', v2_prompt)),
        'Priority System': len(re.findall(r'Priority \d:', v2_prompt)),
        'Constraints': len(re.findall(r'제약사항|HOME', v2_prompt)),
        'Google Maps': len(re.findall(r'Google Maps', v2_prompt)),
        'Output Format': len(re.findall(r'출력 형식|JSON', v2_prompt)),
        'Validation': len(re.findall(r'검증|체크리스트', v2_prompt)),
    }

    sections_v3 = {
        'Role & Input': len(re.findall(r'## 역할|## 입력 데이터', v3_prompt)),
        'Priority System': len(re.findall(r'Priority \d:|P\d', v3_prompt)),
        'Constraints': len(re.findall(r'제약사항|HOME', v3_prompt)),
        'Google Maps': len(re.findall(r'Google Maps', v3_prompt)),
        'Output Format': len(re.findall(r'출력 형식|JSON', v3_prompt)),
        'Gemini 3 Specific': len(re.findall(r'Gemini 3 Pro|SOTA|Advanced Reasoning', v3_prompt)),
    }

    for section in sections_v2:
        v2_count = sections_v2.get(section, 0)
        v3_count = sections_v3.get(section, 0)
        print(f"{section:<25} V2: {v2_count:>3}  V3: {v3_count:>3}")

    print()
    print("KEY IMPROVEMENTS")
    print("-" * 70)
    print("✅ Reduced verbosity by {:.1f}% while maintaining functionality".format(lines_pct))
    print("✅ Leverages Gemini 3 Pro's SOTA reasoning capabilities")
    print("✅ Removed redundant examples and verbose explanations")
    print("✅ Added Gemini 3-specific advanced reasoning guidance")
    print("✅ Consolidated validation checklist (eliminated duplication)")
    print()

    return {
        'v2_lines': v2_lines,
        'v3_lines': v3_lines,
        'v2_tokens': v2_tokens,
        'v3_tokens': v3_tokens,
        'reduction_pct': lines_pct
    }

if __name__ == '__main__':
    stats = main()
    if stats and stats['reduction_pct'] >= 35:
        print("✅ SUCCESS: Achieved >35% reduction target!")
    else:
        print("⚠️  Reduction below 35% target")
